"""Single-owner private API: bearer auth, byte uploads, no arbitrary server paths."""
import os
import secrets
from uuid import UUID

from fastapi import FastAPI, Depends, Header, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from src.storage.models import SourceRegistration, SourceMetadata, SourceFilters
from src.storage.objects import MAX_BYTES


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
                             verify_hallucination=req.verify_hallucination).to_display_dict()

    return app
