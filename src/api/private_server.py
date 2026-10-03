"""Single-owner private API: bearer auth, byte uploads, no arbitrary server paths."""
import os
import secrets
from uuid import UUID
from typing import Literal

from fastapi import FastAPI, Depends, Header, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field, ConfigDict

from src.storage.models import SourceRegistration, SourceMetadata, SourceFilters, ResearchSelection, CollectionRequest
from src.storage.objects import MAX_BYTES
from src.financial.research import ResearchRequest
from src.financial.models import FinancialObservation
from src.financial.evidence import EvidenceSearchRequest


class BodyLimit:
    def __init__(self,app):
        self.app=app
    async def __call__(self,scope,receive,send):
        if scope['type']!='http':
            return await self.app(scope,receive,send)
        size=0
        async def bounded_receive():
            nonlocal size
            message=await receive()
            size+=len(message.get('body',b''))
            if size>MAX_BYTES:
                raise HTTPException(413,'Request exceeds 20 MiB')
            return message
        return await self.app(scope,bounded_receive,send)


class PrivateQuery(BaseModel):
    question: str = Field(min_length=1,max_length=4000)
    filters: SourceFilters = Field(default_factory=SourceFilters)
    verify_hallucination: bool = False
    supplement_k: int = Field(default=0, ge=0, le=8, strict=True)


class VersionMetadataReview(BaseModel):
    metadata: SourceMetadata
    reviewer: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=2000)


class ResearchQuestion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str = Field(min_length=1, max_length=4000)
    selections: tuple[ResearchSelection, ...] = Field(default=(), max_length=18)
    collection_id: UUID | None = None
    save: bool = False
    period_policy: Literal["exact_duration", "reporting_kind"] = "exact_duration"


def build_private_app(service=None, token=None):
    from src.services.persistent_service import PersistentRAGService
    token = token or os.getenv('FINRAG_API_TOKEN')
    if not token or len(token)<24:
        raise RuntimeError('Private API requires FINRAG_API_TOKEN of at least 24 characters')
    service = service or PersistentRAGService(os.environ['DATABASE_URL'],owner=os.getenv('FINRAG_OWNER','default'))

    def authorize(authorization: str | None = Header(None)):
        if not authorization or not secrets.compare_digest(authorization.encode(),('Bearer '+token).encode()):
            raise HTTPException(401,'Unauthorized')

    app = FastAPI(title='FinRAG private sources',dependencies=[Depends(authorize)])
    app.add_middleware(BodyLimit)

    @app.exception_handler(LookupError)
    async def missing(request,exc):
        from starlette.responses import JSONResponse
        return JSONResponse({'detail':'Record not found'},status_code=404)

    @app.exception_handler(ValueError)
    async def invalid(request,exc):
        from starlette.responses import JSONResponse
        return JSONResponse({'detail':str(exc)},status_code=400)

    @app.get('/health')
    def health():
        return jsonable_encoder(service.status())

    @app.post('/sources')
    def register(req: SourceRegistration):
        return jsonable_encoder(service.register(**req.model_dump(mode='json')))

    @app.get('/sources')
    def sources():
        return jsonable_encoder(service.registry.list(service.owner))

    @app.get('/sources/{source_id}')
    def source(source_id: UUID):
        return jsonable_encoder(service.registry.get(service.owner,source_id))

    @app.get('/sources/{source_id}/versions')
    def versions(source_id: UUID):
        return jsonable_encoder(service.registry.versions(service.owner,source_id))

    @app.patch('/sources/{source_id}/metadata')
    def metadata(source_id: UUID, req: SourceMetadata):
        return jsonable_encoder(service.registry.update_metadata(service.owner,source_id,req))

    @app.post('/sources/{source_id}/versions/{version_id}/metadata-reviews')
    def review_version(source_id: UUID, version_id: UUID, req: VersionMetadataReview):
        return jsonable_encoder(service.registry.review_version_metadata(service.owner, source_id, version_id,
            req.metadata, req.reviewer, req.reason))

    @app.get('/sources/{source_id}/versions/{version_id}/metadata-reviews')
    def version_reviews(source_id: UUID, version_id: UUID):
        return jsonable_encoder(service.registry.version_metadata_reviews(service.owner, source_id, version_id))

    @app.post('/sources/{source_id}/suggestions')
    def suggestions(source_id: UUID):
        from src.pipelines.metadata import suggest_metadata
        return suggest_metadata(service,source_id)

    @app.delete('/sources/{source_id}')
    def archive(source_id: UUID):
        return jsonable_encoder(service.registry.archive(service.owner,source_id))

    @app.post('/sources/{source_id}/content')
    async def upload(source_id: UUID, request: Request):
        service.registry.get(service.owner,source_id)
        data = bytearray()
        async for part in request.stream():
            data.extend(part)
            if len(data)>MAX_BYTES:
                raise HTTPException(413,'Upload exceeds 20 MiB')
        # Parsing/model work is performed by the bounded worker, never the event loop.
        from starlette.concurrency import run_in_threadpool
        queued = await run_in_threadpool(service.submit,source_id,bytes(data),
                                        media_type=request.headers.get('content-type','').split(';')[0])
        return {'job_id':str(queued['job']['job_id']),'version_id':str(queued['version']['version_id']),
                'build_id':str(queued['build']['build_id']),'status':queued['job']['status']}

    @app.post('/sources/{source_id}/snapshot')
    def snapshot(source_id: UUID):
        queued = service.snapshot(source_id)
        return {'job_id':str(queued['job']['job_id']),'status':queued['job']['status']}

    @app.get('/jobs/{job_id}')
    def job(job_id: UUID):
        row = service.registry.job(service.owner,job_id)
        return jsonable_encoder({k:row[k] for k in ('job_id','status','attempts','error','usage','lease_until')})

    @app.get('/sources/{source_id}/versions/{version_id}/raw')
    def raw(source_id: UUID, version_id: UUID):
        from starlette.responses import Response
        versions = service.registry.versions(service.owner,source_id)
        version = next((v for v in versions if v['version_id']==version_id),None)
        if not version:
            raise LookupError('Version not found')
        return Response(service.objects.get(version['object_key']),media_type=version['media_type'],
                        headers={'Content-Disposition':'attachment','Cache-Control':'private, no-store',
                                 'X-Content-Type-Options':'nosniff'})

    @app.post('/query')
    def query(req: PrivateQuery):
        return service.query(req.question,filters=req.filters.model_dump(mode='json',exclude_none=True),
                             verify_hallucination=req.verify_hallucination,
                             supplement_k=req.supplement_k).to_display_dict()

    @app.post('/research')
    def research(req: ResearchRequest):
        return service.research(req)

    @app.post('/research/questions')
    def research_question(req: ResearchQuestion):
        return service.research_question(req.question, [s.model_dump(mode='json', exclude_none=True) for s in req.selections],
                                         req.collection_id, req.save, req.period_policy)

    @app.post('/research/evidence')
    def research_evidence(req: EvidenceSearchRequest):
        return service.research_evidence(req)

    @app.post('/research/observations')
    def observation(req: FinancialObservation):
        return service.registry.save_observation(service.owner, req)

    @app.get('/sources/{source_id}/observations')
    def observations(source_id: UUID, version_id: UUID | None = None):
        selection = {'source_id': str(source_id)}
        if version_id:
            selection['version_id'] = str(version_id)
        snapshot = service.registry.research_snapshot(service.owner, [selection])
        return service.registry.observations(service.owner, [p.build_id for p in snapshot['sources']])

    @app.post('/research/collections')
    def create_collection(req: CollectionRequest):
        return jsonable_encoder(service.registry.create_collection(service.owner, req))

    @app.get('/research/collections')
    def collections():
        return jsonable_encoder(service.registry.collections(service.owner))

    @app.post('/research/runs')
    def save_research(req: ResearchRequest):
        return service.research(req, save=True)

    @app.post('/research/evidence/runs')
    def save_evidence(req: EvidenceSearchRequest):
        return service.research_evidence(req, save=True)

    @app.get('/research/runs')
    def research_runs():
        return jsonable_encoder(service.registry.research_runs(service.owner))

    @app.get('/research/runs/{run_id}')
    def research_run(run_id: str):
        row = service.registry.research_run(service.owner, run_id)
        return jsonable_encoder({**row, 'source_changes': service.registry.research_changes(service.owner, row['payload'])})

    @app.post('/research/runs/{run_id}/rerun')
    def rerun_research(run_id: str):
        return service.rerun_research(run_id)

    return app
