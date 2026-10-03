"""Small transactional source registry; remote parsing/model calls stay outside SQL."""
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .models import SourceRegistration, SourceMetadata


def config_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class Registry:
    def __init__(self, dsn):
        self.dsn = dsn

    def connect(self):
        return psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5,
                              options='-c statement_timeout=30000 -c lock_timeout=5000')

    def migrate(self):
        with self.connect() as db:
            db.execute(Path(__file__).with_name('schema.sql').read_text())

    @staticmethod
    def owned(db, owner, source_id, lock=False):
        row = db.execute('SELECT * FROM sources WHERE owner_id=%s AND source_id=%s' +
                         (' FOR UPDATE' if lock else ''), (owner, source_id)).fetchone()
        if not row:
            raise LookupError('Source not found')
        return row

    def register(self, owner, registration):
        from .fetch import normalize_url
        req = SourceRegistration.model_validate(registration)
        if not owner or not req.title.strip():
            raise ValueError('Owner and title must be nonempty')
        if req.kind == 'url':
            req.locator = normalize_url(req.locator or '')
        elif req.locator is not None:
            # A display locator is never a server file path or an object key.
            req.locator = Path(req.locator).name
        values = (owner, req.kind, req.title.strip(), req.locator,
                  Jsonb(req.metadata.model_dump(mode='json')), req.request_key)
        fingerprint=config_hash({'kind':req.kind,'title':req.title.strip(),'locator':req.locator,
                                 'metadata':req.metadata.model_dump(mode='json')})
        with self.connect() as db:
            row = db.execute('''INSERT INTO sources(source_id,owner_id,kind,title,locator,metadata,request_key,registration_hash)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(owner_id,request_key) DO NOTHING RETURNING *''',
                (uuid4(), *values,fingerprint)).fetchone()
            if row:
                return row
            row = db.execute('SELECT * FROM sources WHERE owner_id=%s AND request_key=%s FOR UPDATE',
                             (owner, req.request_key)).fetchone()
            if (row['registration_hash'] and row['registration_hash']!=fingerprint) or any(
                    row[k]!=v for k,v in [('kind',req.kind),('title',req.title.strip()),('locator',req.locator)]):
                raise ValueError('Request key already belongs to a different registration')
            if not row['registration_hash']:
                # Early prototype rows lack the original payload; freeze the first compatible retry.
                db.execute('UPDATE sources SET registration_hash=%s WHERE source_id=%s',(fingerprint,row['source_id']))
            return row

    def list(self, owner, include_archived=False):
        with self.connect() as db:
            return db.execute('SELECT * FROM sources WHERE owner_id=%s AND (%s OR status<>\'archived\') ORDER BY created_at,source_id',
                              (owner, include_archived)).fetchall()

    def get(self, owner, source_id):
        with self.connect() as db:
            return self.owned(db, owner, source_id)

    def versions(self, owner, source_id):
        with self.connect() as db:
            self.owned(db, owner, source_id)
            return db.execute('SELECT * FROM source_versions WHERE source_id=%s ORDER BY number',
                              (source_id,)).fetchall()

    def update_metadata(self, owner, source_id, metadata):
        metadata = SourceMetadata.model_validate(metadata).model_dump(mode='json')
        with self.connect() as db:
            self.owned(db, owner, source_id, True)
            return db.execute('UPDATE sources SET metadata=%s,metadata_revision=metadata_revision+1 WHERE source_id=%s RETURNING *',
                              (Jsonb(metadata), source_id)).fetchone()

    def archive(self, owner, source_id):
        with self.connect() as db:
            self.owned(db, owner, source_id, True)
            return db.execute("UPDATE sources SET status='archived' WHERE source_id=%s RETURNING *",
                              (source_id,)).fetchone()

    def review_version_metadata(self, owner, source_id, version_id, metadata, reviewer, reason):
        metadata = SourceMetadata.model_validate(metadata).model_dump(mode='json')
        if metadata['review_status'] != 'confirmed' or not reviewer.strip() or not reason.strip():
            raise ValueError('Historical corrections require confirmed metadata, reviewer and reason')
        with self.connect() as db:
            source = self.owned(db, owner, source_id, True)
            if source['status'] == 'archived':
                raise ValueError('Archived sources cannot receive metadata reviews')
            if not db.execute('SELECT 1 FROM source_versions WHERE source_id=%s AND version_id=%s',
                              (source_id, version_id)).fetchone():
                raise LookupError('Version not found')
            return db.execute('''INSERT INTO source_version_metadata_reviews
                (review_id,version_id,revision,metadata,reviewer,reason)
                SELECT %s,%s,COALESCE(max(revision),0)+1,%s,%s,%s
                FROM source_version_metadata_reviews WHERE version_id=%s RETURNING *''',
                (uuid4(), version_id, Jsonb(metadata), reviewer.strip(), reason.strip(), version_id)).fetchone()

    def version_metadata_reviews(self, owner, source_id, version_id):
        with self.connect() as db:
            self.owned(db, owner, source_id)
            if not db.execute('SELECT 1 FROM source_versions WHERE source_id=%s AND version_id=%s',
                              (source_id, version_id)).fetchone():
                raise LookupError('Version not found')
            return db.execute('SELECT * FROM source_version_metadata_reviews WHERE version_id=%s ORDER BY revision',
                              (version_id,)).fetchall()

    def research_snapshot(self, owner, selections):
        """Resolve all authorized versions/builds and original blocks in one read snapshot."""
        from src.core.models import DocumentBlock
        from src.financial.models import PinnedSource
        from .models import ResearchSelection
        from uuid import UUID
        filters = [ResearchSelection.model_validate(item) for item in selections]
        if not 1 <= len(filters) <= 18 or any(f.source_id is None for f in filters):
            raise ValueError('Research requires 1–18 explicit source selections')
        if len({f.source_id for f in filters}) != len(filters):
            raise ValueError('Select each source once')
        pins, blocks, inventory = [], {}, []
        with self.connect() as db:
            db.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            for f in filters:
                source = self.owned(db, owner, f.source_id)
                if source['status'] == 'archived':
                    raise LookupError('Source not found')
                version_id = f.version_id or source['active_version_id']
                row = db.execute('''SELECT v.*, b.build_id,b.status AS build_status,
                    r.metadata AS reviewed_metadata,r.review_id,r.revision AS review_revision
                    FROM source_versions v LEFT JOIN retrieval_builds b ON b.build_id=COALESCE(%s,v.active_build_id) AND b.version_id=v.version_id
                    LEFT JOIN LATERAL (SELECT * FROM source_version_metadata_reviews
                        WHERE version_id=v.version_id AND (%s::uuid IS NULL OR review_id=%s)
                        ORDER BY revision DESC LIMIT 1) r ON true
                    WHERE v.source_id=%s AND v.version_id=%s''',
                    (f.build_id, f.metadata_review_id, f.metadata_review_id, f.source_id, version_id)).fetchone()
                if f.version_id and not row:
                    raise LookupError('Version not found')
                if f.build_id and (not row or not row['build_id']):
                    raise LookupError('Build not found')
                if f.metadata_review_id and (not row or not row['review_id']):
                    raise LookupError('Metadata review not found')
                metadata = (row['reviewed_metadata'] or row['metadata']) if row and f.version_id else source['metadata']
                inventory.append({'source_id': str(f.source_id), 'title': source['title'],
                    'status': source['status'], 'metadata': metadata,
                    'version_id': str(version_id) if version_id else None,
                    'metadata_review_id': str(row['review_id']) if f.version_id and row and row['review_id'] else None,
                    'metadata_review_revision': row['review_revision'] if f.version_id and row else None,
                    'source_metadata_revision': source['metadata_revision'] if not f.version_id else None,
                    'last_error': source['last_error']})
                if not row or not row['build_id'] or row['build_status'] != 'ready':
                    continue
                if metadata.get('review_status') != 'confirmed' or not metadata.get('company_id'):
                    continue
                for field in ('company_id', 'fiscal_year', 'fiscal_quarter', 'document_type'):
                    if getattr(f, field) is not None and str(metadata.get(field)) != str(getattr(f, field)):
                        raise ValueError('Selected source does not match requested metadata')
                pin = PinnedSource(source_id=str(f.source_id), version_id=str(row['version_id']),
                    build_id=str(row['build_id']), source_hash=row['sha256'], company_id=metadata['company_id'],
                    publication_date=metadata.get('publication_date'))
                pins.append(pin)
            if pins:
                rows = db.execute('''SELECT build_id,payload FROM blocks
                    WHERE build_id=ANY(%s) ORDER BY build_id,ordinal LIMIT 10001''',
                    ([UUID(p.build_id) for p in pins],)).fetchall()
                if len(rows) > 10000:
                    raise ValueError('Research exceeds 10000 original blocks')
                blocks = {p.build_id: [] for p in pins}
                for row in rows:
                    blocks[str(row['build_id'])].append(DocumentBlock.model_validate(row['payload']))
        return {'sources': pins, 'blocks': blocks, 'inventory': inventory}

    def enqueue(self, owner, source_id, data, object_key, media_type, provenance, manifest):
        sha = hashlib.sha256(data).hexdigest()
        with self.connect() as db:
            source = self.owned(db, owner, source_id, True)
            if source['status'] == 'archived':
                raise ValueError('Archived sources cannot be ingested')
            version = db.execute('SELECT * FROM source_versions WHERE source_id=%s AND sha256=%s',
                                 (source_id, sha)).fetchone()
            if version is None:
                last = db.execute('SELECT version_id,number FROM source_versions WHERE source_id=%s ORDER BY number DESC LIMIT 1',
                                  (source_id,)).fetchone()
                metadata=dict(source['metadata'])
                if source['active_version_id']:
                    metadata['review_status']='needs_review'
                provenance={**provenance,'metadata_revision':source['metadata_revision']}
                version = db.execute('''INSERT INTO source_versions(version_id,source_id,number,sha256,
                    object_key,media_type,size_bytes,metadata,provenance,supersedes_version_id)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
                    (uuid4(), source_id, last['number']+1 if last else 1, sha, object_key, media_type,
                     len(data), Jsonb(metadata), Jsonb(provenance), last['version_id'] if last else None)).fetchone()
            build = db.execute('''INSERT INTO retrieval_builds(build_id,version_id,config_hash,manifest)
                VALUES(%s,%s,%s,%s) ON CONFLICT(version_id,config_hash) DO UPDATE SET config_hash=EXCLUDED.config_hash RETURNING *''',
                (uuid4(), version['version_id'], config_hash(manifest), Jsonb(manifest))).fetchone()
            job = db.execute('''INSERT INTO ingestion_jobs(job_id,build_id) VALUES(%s,%s)
                ON CONFLICT(build_id) DO UPDATE SET build_id=EXCLUDED.build_id RETURNING *''',
                (uuid4(), build['build_id'])).fetchone()
            db.execute('UPDATE sources SET desired_build_id=%s,last_error=NULL WHERE source_id=%s', (build['build_id'], source_id))
            if build['status'] == 'ready':
                db.execute("UPDATE sources SET active_version_id=%s,active_build_id=%s,status='ready' WHERE source_id=%s",
                           (version['version_id'], build['build_id'], source_id))
            elif not source['active_build_id']:
                db.execute("UPDATE sources SET status='pending' WHERE source_id=%s", (source_id,))
            return {'source': source, 'version': version, 'build': build, 'job': job}

    def claim(self, owner, job_id, lease_seconds=900):
        token = uuid4()
        with self.connect() as db:
            row = db.execute('''UPDATE ingestion_jobs j SET status='processing',lease_token=%s,
                lease_until=now()+%s*interval '1 second',attempts=attempts+1,error=NULL
                FROM retrieval_builds b,source_versions v,sources s
                WHERE j.job_id=%s AND j.build_id=b.build_id AND b.version_id=v.version_id
                AND v.source_id=s.source_id AND s.owner_id=%s AND s.status<>'archived'
                AND (j.status IN ('pending','failed') OR (j.status='processing' AND j.lease_until<now())) RETURNING j.*''',
                (token, lease_seconds, job_id, owner)).fetchone()
            return row

    def fail(self, owner, job_id, token, reason, usage):
        with self.connect() as db:
            row = db.execute('''UPDATE ingestion_jobs j SET status='failed',error=%s,usage=%s,
                lease_token=NULL,lease_until=NULL FROM retrieval_builds b,source_versions v,sources s
                WHERE j.job_id=%s AND j.lease_token=%s AND j.build_id=b.build_id AND b.version_id=v.version_id
                AND v.source_id=s.source_id AND s.owner_id=%s RETURNING j.build_id,v.source_id''',
                (reason, Jsonb(usage), job_id, token, owner)).fetchone()
            if row:
                db.execute("UPDATE retrieval_builds SET status='failed' WHERE build_id=%s", (row['build_id'],))
                db.execute("UPDATE sources SET last_error=%s,status=CASE WHEN status='archived' THEN status WHEN active_build_id IS NULL THEN 'failed' ELSE 'ready' END WHERE source_id=%s AND desired_build_id=%s",
                           (reason, row['source_id'], row['build_id']))

    def job(self, owner, job_id):
        with self.connect() as db:
            row = db.execute('''SELECT j.*,b.manifest,b.version_id,v.source_id,v.sha256,v.object_key,
                v.media_type,v.metadata,s.title,s.kind FROM ingestion_jobs j
                JOIN retrieval_builds b USING(build_id) JOIN source_versions v USING(version_id)
                JOIN sources s USING(source_id) WHERE j.job_id=%s AND s.owner_id=%s''', (job_id, owner)).fetchone()
            if not row:
                raise LookupError('Job not found')
            return row

    def publish(self, owner, job_id, token, document, parents, children, vectors, usage):
        import math
        if not children or len(children) != len(vectors) or not parents:
            raise ValueError('Build must contain parents and matching child vectors')
        ids = {c.chunk_id for c in parents+children}
        parent_ids = {c.chunk_id for c in parents}
        if len(ids) != len(parents)+len(children) or any(c.parent_chunk_id not in parent_ids for c in children):
            raise ValueError('Duplicate chunks or missing parent')
        blocks = {b.block_id: b for b in document.blocks}
        for c in parents+children:
            if not c.evidence_spans or c.source_version != document.source_hash or c.document_id != document.document_id:
                raise ValueError('Missing source provenance')
            for span in c.evidence_spans:
                b = blocks.get(span.block_id)
                body = (b.get_original_text() or b.semantic_content or '') if b else ''
                if span.source_version != document.source_hash or not 0 <= span.char_start < span.char_end <= len(body) or body[span.char_start:span.char_end] != span.text:
                    raise ValueError('Invalid evidence span')
        with self.connect() as db:
            job = db.execute('''SELECT j.*,b.manifest,b.version_id,v.source_id,v.sha256,s.owner_id
                FROM ingestion_jobs j JOIN retrieval_builds b USING(build_id)
                JOIN source_versions v USING(version_id) JOIN sources s USING(source_id)
                WHERE j.job_id=%s AND s.owner_id=%s FOR UPDATE OF j,s''', (job_id, owner)).fetchone()
            if not job or job['lease_token'] != token or job['status'] != 'processing':
                raise RuntimeError('Job lease was lost')
            live = db.execute('SELECT lease_until>now() AS valid FROM ingestion_jobs WHERE job_id=%s', (job_id,)).fetchone()
            if not live['valid']:
                raise RuntimeError('Job lease expired')
            if document.source_hash != job['sha256'] or document.document_id != str(job['source_id']):
                raise ValueError('Document does not belong to this job')
            dimensions = job['manifest']['dimensions']
            if any(len(v) != dimensions or not all(math.isfinite(x) for x in v) or not any(v) for v in vectors):
                raise ValueError('Invalid embedding dimensions or values')
            build_id = job['build_id']
            for ordinal,b in enumerate(document.blocks):
                db.execute('INSERT INTO blocks(build_id,block_id,ordinal,payload) VALUES(%s,%s,%s,%s)',
                           (build_id, b.block_id, ordinal, Jsonb(b.model_dump(mode='json'))))
            for ordinal, c in enumerate(parents+children):
                retrieval = c.retrieval_text or c.text
                db.execute('''INSERT INTO chunks(build_id,chunk_id,parent_id,ordinal,payload,retrieval_text,input_hash)
                    VALUES(%s,%s,%s,%s,%s,%s,%s)''', (build_id,c.chunk_id,c.parent_chunk_id,ordinal,
                    Jsonb(c.model_dump(mode='json')),retrieval,hashlib.sha256(retrieval.encode()).hexdigest()))
            for child, vector in zip(children, vectors):
                db.execute('''INSERT INTO chunk_embeddings(build_id,chunk_id,model,dimensions,input_hash,embedding)
                    VALUES(%s,%s,%s,%s,%s,%s::vector)''', (build_id,child.chunk_id,job['manifest']['embedding_model'],dimensions,
                    hashlib.sha256((child.retrieval_text or child.text).encode()).hexdigest(),json.dumps(vector)))
            db.execute("UPDATE retrieval_builds SET status='ready' WHERE build_id=%s", (build_id,))
            db.execute('UPDATE source_versions SET active_build_id=%s WHERE version_id=%s', (build_id,job['version_id']))
            db.execute("UPDATE ingestion_jobs SET status='ready',usage=%s,lease_token=NULL,lease_until=NULL,error=NULL WHERE job_id=%s",
                       (Jsonb(usage), job_id))
            # A newer request or an archive wins over a late worker.
            version=db.execute('SELECT metadata,provenance FROM source_versions WHERE version_id=%s',(job['version_id'],)).fetchone()
            return db.execute("""UPDATE sources SET active_version_id=%s,active_build_id=%s,status='ready',last_error=NULL,
                metadata=CASE WHEN metadata_revision=%s THEN %s ELSE metadata END
                WHERE source_id=%s AND desired_build_id=%s AND status<>'archived' RETURNING *""",
                (job['version_id'],build_id,version['provenance'].get('metadata_revision',0),Jsonb(version['metadata']),job['source_id'],build_id)).fetchone()
