"""Exact pgvector + filtered BM25/SQL lexical ranking over one database snapshot."""
import json
import math

from src.core.models import DocumentChunk
from src.storage.models import SourceFilters
from .bm25 import BM25Retriever
from .rrf import rrf_merge
from .hybrid import supplement_parent_evidence

MAX_CHILDREN = 10000


class PostgresRetriever:
    name = 'postgres_hybrid'

    def __init__(self, registry, owner, embeddings, model, dimensions, filters=None, lexical='bm25'):
        self.registry, self.owner, self.embeddings = registry, owner, embeddings
        self.model, self.dimensions = model, dimensions
        self.filters = SourceFilters.model_validate(filters or {})
        if lexical not in ('bm25', 'postgres'):
            raise ValueError('Unknown lexical branch')
        self.lexical = lexical

    def retrieve(self, query, k=5):
        return self.retrieve_with_candidates(query, k)['chunks']

    def retrieve_with_candidates(self, query, k=5, fetch_k=20, use_parent=True, supplement_k=0):
        f = self.filters
        vector = self.embeddings.embed_query(query)
        if len(vector) != self.dimensions or not all(math.isfinite(x) for x in vector) or not any(vector):
            raise ValueError('Query embedding profile mismatch')
        where, args = ['s.owner_id=%s', "s.status<>'archived'", "b.status='ready'"], [self.owner]
        if f.version_id:
            where.extend(['v.source_id=s.source_id', 'v.version_id=%s', 'b.build_id=v.active_build_id'])
            args.append(f.version_id)
        else:
            where.extend(['v.version_id=s.active_version_id', 'b.build_id=s.active_build_id'])
        if f.source_id:
            where.append('s.source_id=%s'); args.append(f.source_id)
        metadata_expr = 'COALESCE(mr.metadata,v.metadata)' if f.version_id else 's.metadata'
        for field in ('company_id','fiscal_year','fiscal_quarter','document_type'):
            value = getattr(f, field)
            if value is not None:
                where.extend([metadata_expr+"->>'review_status'='confirmed'", metadata_expr+'->>%s=%s'])
                args.extend([field, str(value)])
        with self.registry.connect() as db:
            db.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            review_join = ''' LEFT JOIN LATERAL (SELECT metadata FROM source_version_metadata_reviews
                WHERE version_id=v.version_id ORDER BY revision DESC LIMIT 1) mr ON true''' if f.version_id else ''
            builds = db.execute('SELECT b.*,'+metadata_expr+' AS source_metadata FROM sources s,source_versions v'+review_join+',retrieval_builds b WHERE b.version_id=v.version_id AND '+
                                ' AND '.join(where), args).fetchall()
            if not builds:
                return {'chunks': [], 'candidates': []}
            if any(b['manifest']['embedding_model'] != self.model or b['manifest']['dimensions'] != self.dimensions or
                   b['manifest'].get('distance') != 'cosine' for b in builds):
                raise ValueError('Active build embedding profile differs from runtime')
            build_ids = [b['build_id'] for b in builds]
            source_metadata = {str(b['build_id']): b['source_metadata'] for b in builds
                               if (b.get('source_metadata') or {}).get('review_status') == 'confirmed'}
            rows = db.execute('SELECT payload,parent_id FROM chunks WHERE build_id=ANY(%s) ORDER BY build_id,ordinal LIMIT %s',
                              (build_ids, MAX_CHILDREN*2+1)).fetchall()
            children = [DocumentChunk.model_validate(r['payload']) for r in rows if r['parent_id']]
            # ponytail: bounded in-memory BM25 compatibility; switch only after lexical parity passes.
            if len(rows) > MAX_CHILDREN*2 or len(children) > MAX_CHILDREN:
                raise ValueError('Corpus exceeds the 10000-child compatibility limit')
            parents = {r['payload']['chunk_id']: DocumentChunk.model_validate(r['payload']) for r in rows if not r['parent_id']}
            vectors = db.execute('''SELECT c.payload,e.embedding <=> %s::vector AS distance
                FROM chunks c JOIN chunk_embeddings e USING(build_id,chunk_id)
                WHERE c.build_id=ANY(%s) AND e.model=%s AND e.dimensions=%s AND e.input_hash=c.input_hash
                ORDER BY distance,c.chunk_id LIMIT %s''', (json.dumps(vector),build_ids,self.model,self.dimensions,fetch_k)).fetchall()
            vec_scored = [(DocumentChunk.model_validate(r['payload']), 1-r['distance']) for r in vectors]
            if self.lexical == 'postgres':
                from .bm25 import _tokenize
                tokens = _tokenize(query)
                tsquery = ' | '.join(tokens)
                rows = db.execute('''SELECT payload,ts_rank_cd(lexical,to_tsquery('simple',%s)) AS score
                    FROM chunks WHERE build_id=ANY(%s) AND parent_id IS NOT NULL
                    AND lexical @@ to_tsquery('simple',%s) ORDER BY score DESC,chunk_id LIMIT %s''',
                    (tsquery,build_ids,tsquery,fetch_k)).fetchall() if tokens else []
                lex_scored = [(DocumentChunk.model_validate(r['payload']),r['score']) for r in rows]
            else:
                bm25 = BM25Retriever(); bm25.index(children)
                lex_scored = bm25.search_with_scores(query, fetch_k)
        fused = rrf_merge([vec_scored,lex_scored], top_n=fetch_k)
        candidates = [c.model_copy(update={'metadata': {**c.metadata,'rrf_score': score}}) for c,score in fused]
        result, seen = [], set()
        for c in candidates:
            target = parents[c.parent_chunk_id] if use_parent else c
            if target.chunk_id not in seen:
                seen.add(target.chunk_id); result.append(target)
            if len(result) >= k:
                break
        if use_parent:
            result = supplement_parent_evidence(query, result, candidates, parents, supplement_k)
        # Request-only aliases come from the same authorized source/version snapshot.
        enriched = []
        for chunk in result:
            metadata = {k: v for k, v in chunk.metadata.items() if k != 'confirmed_source_metadata'}
            confirmed = source_metadata.get(str(metadata.get('build_id')))
            if confirmed:
                metadata['confirmed_source_metadata'] = dict(confirmed)
            enriched.append(chunk.model_copy(update={'metadata': metadata}))
        result = enriched
        return {'chunks': result, 'candidates': candidates}
