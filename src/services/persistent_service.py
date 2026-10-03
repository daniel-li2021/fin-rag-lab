"""Opt-in durable application path; the local notebook service stays usable."""
import copy
import hashlib
import os
from pathlib import Path
import tempfile

from src.captioners.vlm_captioner import NoOpCaptioner
from src.core.cache import make_cached_embeddings
from src.core.config import settings
from src.observability.embeddings import make_tracked_embeddings
from src.loaders.text_loader import load_text
from src.storage.objects import LocalObjects, S3Objects, MAX_BYTES
from src.storage.registry import Registry
from src.retrievers.postgres import PostgresRetriever
from src.generators import RAGGenerator
from src.pipelines import QueryPipeline
from .rag_service import RAGService, IndexedDocument, IndexStatus

MEDIA = {'pdf': 'application/pdf', 'text': 'text/plain', 'markdown': 'text/markdown'}


class PersistentRAGService(RAGService):
    def __init__(self, dsn, owner='default', objects=None, embeddings=None,
                 embedding_model=None, dimensions=1536, **kwargs):
        # Plain text/tables need no VLM. An explicitly supplied captioner is reused.
        kwargs.setdefault('captioner', NoOpCaptioner())
        kwargs.setdefault('enable_langsmith', False)
        if os.getenv('FINRAG_ALLOW_TRACING')!='true':
            os.environ['LANGSMITH_TRACING']='false'
        super().__init__(**kwargs)
        self.registry, self.owner = Registry(dsn), owner
        self.objects = objects or (S3Objects(os.environ['FINRAG_BUCKET']) if os.getenv('FINRAG_BUCKET')
                                  else LocalObjects(os.getenv('FINRAG_OBJECT_DIR', self.index_dir/'objects')))
        self.embedding_model = embedding_model or settings.embedding_model
        self.dimensions = dimensions
        self.embeddings = embeddings or make_cached_embeddings(
            make_tracked_embeddings(self.embedding_model,self.cost_tracker),
            self.cache.embeddings_dir,self.embedding_model)

    def register(self, **registration):
        return self.registry.register(self.owner,registration)

    def manifest(self, max_pages=100, page_range=None):
        from src.storage.registry import config_hash
        # Parser/chunker changes create a new build even for unchanged bytes.
        files = [p for folder in ('parsers','loaders','chunkers','captioners')
                 for p in sorted((settings.repo_root/'src'/folder).glob('*.py'))]
        files.extend(settings.repo_root/'src'/name for name in ('core/cache.py','core/models.py','pipelines/ingestion.py'))
        return {'schema_revision': 1, 'evidence_revision': 1, 'embedding_model': self.embedding_model,
                'dimensions': self.dimensions, 'distance': 'cosine', 'normalization': 'provider',
                'parent_size': self.parent_size, 'child_size': self.child_size,
                'parent_overlap': self.chunker.parent_overlap, 'child_overlap': self.chunker.child_overlap,
                'parser': self.ingestion.parser.name,
                'parser_configuration': {k:v for k,v in vars(self.ingestion.parser).items() if isinstance(v,(str,int,float,bool,type(None)))},
                'derived_code_hash': config_hash({str(p.relative_to(settings.repo_root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}),
                'captioner': getattr(self.ingestion.captioner,'model',self.ingestion.captioner.name),
                'max_pages': max_pages, 'page_range': list(page_range) if page_range else None}

    def submit(self, source_id, data, media_type=None, provenance=None, max_pages=100, page_range=None):
        source = self.registry.get(self.owner,source_id)
        media = media_type or MEDIA.get(source['kind'])
        allowed = set(MEDIA.values()) | {'text/html'} if source['kind']=='url' else {MEDIA[source['kind']]}
        if media not in allowed or not data or len(data)>MAX_BYTES:
            raise ValueError('Invalid content media type or size')
        if media == 'application/pdf' and not data.startswith(b'%PDF-'):
            raise ValueError('PDF signature is missing')
        if media != 'application/pdf':
            load_text(data, {'text/plain':'text','text/markdown':'markdown','text/html':'html'}[media],source['title'])
        if max_pages is None or not 1 <= max_pages <= 100:
            raise ValueError('PDF page cap must be between 1 and 100')
        if page_range and (page_range[0]<1 or page_range[1]<page_range[0] or page_range[1]-page_range[0]+1>max_pages):
            raise ValueError('Invalid PDF page range')
        key = self.objects.put(self.owner,data,media)
        return self.registry.enqueue(self.owner,source_id,data,key,media,provenance or {},self.manifest(max_pages,page_range))

    def snapshot(self, source_id):
        from src.storage.fetch import fetch_snapshot
        source = self.registry.get(self.owner,source_id)
        if source['kind'] != 'url' or source['status']=='archived':
            raise ValueError('Expected an active URL source')
        try:
            data,media,provenance = fetch_snapshot(source['locator'])
            return self.submit(source_id,data,media,provenance)
        except Exception:
            with self.registry.connect() as db:
                db.execute("UPDATE sources SET last_error='Snapshot fetch failed',status=CASE WHEN active_build_id IS NULL THEN 'failed' ELSE status END WHERE source_id=%s AND status<>'archived'",
                           (source_id,))
            raise

    def process_job(self, job_id):
        job = self.registry.job(self.owner,job_id)
        if job['status']=='ready':
            return {'status':'ready','reused':True,'job_id':str(job_id)}
        claimed = self.registry.claim(self.owner,job_id)
        if claimed is None:
            return {'status':'busy','job_id':str(job_id)}
        token = claimed['lease_token']
        with self.cost_tracker.request() as receipt:
            stage='load'
            try:
                manifest = job['manifest']
                if manifest != self.manifest(manifest['max_pages'],manifest['page_range']):
                    raise ValueError('Worker configuration differs from queued build; resubmit with current configuration')
                data = self.objects.get(job['object_key'])
                if hashlib.sha256(data).hexdigest()!=job['sha256']:
                    raise ValueError('Raw source hash mismatch')
                if job['media_type']=='application/pdf':
                    stage='parse'
                    with tempfile.TemporaryDirectory() as folder:
                        path = Path(folder)/'source.pdf'; path.write_bytes(data)
                        doc = self.ingestion.ingest(path,max_pages=manifest['max_pages'],page_range=manifest['page_range']).document.model_copy(deep=True)
                else:
                    stage='parse'
                    doc = load_text(data,{'text/plain':'text','text/markdown':'markdown','text/html':'html'}[job['media_type']],job['title'])
                doc.document_id,doc.title,doc.source_hash = str(job['source_id']),job['title'],job['sha256']
                doc.tenant_id,doc.source_path = self.owner,job['object_key']
                stage='chunk'
                parents,children = self.chunker.chunk_with_parents(doc)
                if not children or len(children)>3000:
                    raise ValueError('Build must contain 1–3000 children')
                # Remap parent pointers after assigning stable build-scoped IDs.
                mapping = {c.chunk_id:hashlib.sha256(f'{job["build_id"]}:{i}'.encode()).hexdigest()
                           for i,c in enumerate(parents+children)}
                for c in parents+children:
                    c.chunk_id = mapping[c.chunk_id]
                    if c.parent_chunk_id:
                        c.parent_chunk_id = mapping[c.parent_chunk_id]
                    c.metadata.update(source_id=str(job['source_id']),version_id=str(job['version_id']),build_id=str(job['build_id']))
                stage='embedding'
                vectors = self.embeddings.embed_documents([c.retrieval_text or c.text for c in children])
                stage='publish'
                activated = self.registry.publish(self.owner,job_id,token,doc,parents,children,vectors,receipt.report())
                return {'status':'ready','activated':bool(activated),'reused':False,'job_id':str(job_id),
                        'n_blocks':len(doc.blocks),'n_parents':len(parents),'n_children':len(children),'usage':receipt.report()}
            except Exception as exc:
                self.registry.fail(self.owner,job_id,token,f'{stage}: {type(exc).__name__}',receipt.report())
                raise

    def ingest_bytes(self, source_id, data, **options):
        queued = self.submit(source_id,data,**options)
        return self.process_job(queued['job']['job_id'])

    def ingest_and_index(self, sources, *, max_pages=100, page_range=None, **kwargs):
        results = []
        for raw in sources:
            path = Path(raw).resolve()
            kind = {'.pdf':'pdf','.txt':'text','.md':'markdown'}.get(path.suffix.lower())
            if not kind:
                raise ValueError('Supported files: PDF, UTF-8 text and Markdown')
            source = self.register(kind=kind,title=path.stem,locator=path.name,
                                   request_key='path:'+hashlib.sha256(str(path).encode()).hexdigest())
            results.append(self.ingest_bytes(source['source_id'],path.read_bytes(),max_pages=max_pages or 100,page_range=page_range))
        return {'results':results,'n_documents':len(self.registry.list(self.owner))}

    def status(self):
        sources = self.registry.list(self.owner)
        with self.registry.connect() as db:
            counts = db.execute('''SELECT count(*) FILTER(WHERE c.parent_id IS NOT NULL) AS children,
                count(*) FILTER(WHERE c.parent_id IS NULL) AS parents FROM sources s JOIN chunks c
                ON c.build_id=s.active_build_id WHERE s.owner_id=%s AND s.status<>'archived' ''',(self.owner,)).fetchone()
        return IndexStatus(ready=any(s['active_build_id'] for s in sources),index_dir='postgres',
            n_documents=len(sources),n_parents=counts['parents'],n_children=counts['children'],
            documents=[{'document_id':str(s['source_id']),'title':s['title'],'source_path':s['locator'] or '',
                        'kind':s['kind'],'status':s['status'],'metadata':s['metadata']} for s in sources],
            openai_key_set=settings.has_openai_key)

    def is_ready(self):
        return self.status().ready

    def load_index(self):
        with self.registry.connect() as db:
            profiles=db.execute('''SELECT b.manifest FROM sources s JOIN retrieval_builds b ON b.build_id=s.active_build_id
                WHERE s.owner_id=%s AND s.status<>'archived' ''',(self.owner,)).fetchall()
        if any(p['manifest']['embedding_model']!=self.embedding_model or p['manifest']['dimensions']!=self.dimensions for p in profiles):
            raise ValueError('Active build embedding profile differs from runtime')
        return self.is_ready()

    def query(self, question, *, filters=None, lexical='bm25', **options):
        from src.storage.models import SourceFilters
        filters=SourceFilters.model_validate(filters or {}).model_dump(mode='json',exclude_none=True)
        # Each request has its own pipeline/filters; shared service fields never mutate.
        view = copy.copy(self)
        view.documents = [IndexedDocument(str(s['source_id']),s['title'],s['locator'] or '',0,0,0,0)
                          for s in self.registry.list(self.owner)]
        view.vector = type('Profile',(),{'embedding_model':self.embedding_model})()
        view.generator = RAGGenerator(cost_tracker=self.cost_tracker)
        from src.core.config import make_chat_llm
        view.generator._llm=make_chat_llm(view.generator.model,timeout=60,max_retries=0,
            model_kwargs={'max_completion_tokens':4096,'response_format':{'type':'json_object'}})
        retriever = PostgresRetriever(self.registry,self.owner,self.embeddings,self.embedding_model,self.dimensions,filters,lexical)
        view.query_pipeline = QueryPipeline(retriever,view.generator,cost_tracker=self.cost_tracker)
        view.is_ready = lambda: True  # Empty authorized corpora reach the structured refusal path.
        result = RAGService.query(view,question,**options)
        result.configuration.update(backend='postgres',lexical=lexical,filters=filters)
        return result

    def research(self, request, *, save=False, collection_id=None, parent_run_id=None):
        from src.financial.research import ResearchRequest
        request = ResearchRequest.model_validate(request)
        snapshot = self.registry.research_snapshot(self.owner, [s.model_dump(mode='json', exclude_none=True)
                                                              for s in request.selections])
        return self._execute_research(request, snapshot, save, collection_id, parent_run_id)

    def _execute_research(self, request, snapshot, save=False, collection_id=None, parent_run_id=None):
        from src.financial.research import ResearchRequest
        filters = []
        for task in request.tasks:
            period = task.period.model_dump(mode='json')
            if task.period.calendar != 'unresolved':
                period.pop('fiscal_label')
            filters.append({'company_id': task.company_id, 'metric_id': task.metric_id,
                            'scope': task.scope, 'basis': task.basis, 'period': period})
        stored = self.registry.observations(self.owner, [p.build_id for p in snapshot['sources']], filters,
                                            [o.observation_id for o in request.observations])
        if len(stored) > 100:
            raise ValueError('Matching reviewed library exceeds 100 cards; narrow the tasks or source selection')
        observations = {o['observation_id']: o for o in stored}
        for observation in request.observations:
            previous = observations.get(observation.observation_id)
            if previous and previous != observation.model_dump(mode='json'):
                raise ValueError('Request conflicts with an immutable stored observation')
            observations[observation.observation_id] = observation.model_dump(mode='json')
        request = ResearchRequest.model_validate({**request.model_dump(mode='json'), 'observations': list(observations.values())})
        result = QueryPipeline(None, None).research(request, snapshot)
        if save:
            self._save_research_result(result, collection_id, parent_run_id)
        return result

    def _save_research_result(self, result, collection_id=None, parent_run_id=None):
        import uuid
        from datetime import datetime, timezone
        from src.financial.research import _canonical
        result['execution'] = {'execution_id': str(uuid.uuid4()), 'timestamp': datetime.now(timezone.utc).isoformat(),
                               'parent_run_id': parent_run_id, 'collection_id': str(collection_id) if collection_id else None}
        result['run_id'] = hashlib.sha256(_canonical({k: v for k, v in result.items() if k != 'run_id'}).encode()).hexdigest()
        self.registry.save_research(self.owner, result, collection_id, parent_run_id)

    def research_evidence(self, request, *, save=False, collection_id=None, parent_run_id=None):
        from src.financial.evidence import EvidenceSearchRequest
        request = EvidenceSearchRequest.model_validate(request)
        snapshot = self.registry.research_snapshot(self.owner, [s.model_dump(mode='json', exclude_none=True) for s in request.selections])
        result = QueryPipeline(None, None).evidence(request, snapshot)
        if save:
            self._save_research_result(result, collection_id, parent_run_id)
        return result

    def research_question(self, question, selections=None, collection_id=None, save=False, period_policy="exact_duration"):
        from src.financial.intent import resolve_question, parse_question, question_filters
        from src.financial.models import FinancialObservation
        from src.financial.research import ResearchRequest
        if period_policy not in ("exact_duration", "reporting_kind"):
            raise ValueError("Unsupported period policy")
        if collection_id:
            if selections:
                raise ValueError('Choose a collection or explicit selections')
            collection = self.registry.collection(self.owner, collection_id)
            selections = [{'source_id': source_id} for source_id in collection['source_ids']]
        snapshot = self.registry.research_snapshot(self.owner, selections or [])
        parsed = parse_question(question, snapshot['inventory'])
        if 'outcome' in parsed:
            resolution = parsed
        else:
            stored = self.registry.observations(self.owner, [p.build_id for p in snapshot['sources']], question_filters(parsed))
            if len(stored) > 100:
                raise ValueError('Matching reviewed library exceeds 100 cards; narrow the tasks or source selection')
            resolution = resolve_question(question, selections, snapshot['inventory'],
                [FinancialObservation.model_validate(o) for o in stored], parsed)
        if 'request' not in resolution:
            result = {**resolution, 'contract_version': 'research-question-v1',
                'request': {'question': question, 'selections': selections or [], 'period_policy': period_policy},
                'manifest': [s.model_dump(mode='json') for s in snapshot['sources']],
                'inventory': snapshot['inventory'], 'calculations': [], 'calculation_gaps': []}
            from src.financial.research import _canonical
            result['run_id'] = hashlib.sha256(_canonical(result).encode()).hexdigest()
            if save:
                self._save_research_result(result, collection_id)
            return result
        for calculation in resolution['request']['calculations']:
            calculation['period_policy'] = period_policy
        return self._execute_research(ResearchRequest.model_validate(resolution['request']), snapshot,
                                      save=save, collection_id=collection_id)

    def rerun_research(self, run_id):
        previous = self.registry.research_run(self.owner, run_id)['payload']
        request = previous['request']
        # Explicit rerun uses current source pointers and fresh reviewed cards, preserving history.
        request = {**request, 'selections': [{'source_id': s['source_id']} for s in request['selections']]}
        collection_id = previous.get('execution', {}).get('collection_id')
        if previous['contract_version'] == 'research-question-v1':
            current = self.research_question(request['question'], selections=request['selections'],
                period_policy=request.get('period_policy', 'exact_duration'))
            self._save_research_result(current, collection_id, run_id)
        else:
            execute = self.research_evidence if previous['contract_version'] == 'evidence-search-v1' else self.research
            current = execute(request, save=True, parent_run_id=run_id, collection_id=collection_id)
        def evidence_identity(result):
            return result['manifest'], [{k: item.get(k) for k in (
                'source_id', 'version_id', 'metadata_review_id', 'source_metadata_revision', 'metadata')}
                for item in result['inventory']]
        return {'result': current, 'diff': {'previous_outcome': previous['outcome'], 'current_outcome': current['outcome'],
            'answer_changed': previous['answer'] != current['answer'],
            'evidence_changed': evidence_identity(previous) != evidence_identity(current),
            'refresh_failed': any(item.get('last_error') for item in current['inventory']),
            'previous_coverage': previous['coverage'], 'current_coverage': current['coverage'],
            'previous_calculations': previous['calculations'], 'current_calculations': current['calculations']}}
