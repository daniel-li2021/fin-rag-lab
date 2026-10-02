"""Real Postgres/pgvector lifecycle and restore checks; all embeddings are offline."""
from pathlib import Path
import hashlib
import json
import tempfile
import shutil
from concurrent.futures import ThreadPoolExecutor

import pytest

from src.services.persistent_service import PersistentRAGService
from src.storage.objects import LocalObjects
from src.retrievers.postgres import PostgresRetriever


class Embeddings:
    calls = 0
    def embed_documents(self,texts):
        self.calls += 1
        return [[1.,float('revenue' in t.lower()),float('cash' in t.lower())] for t in texts]
    def embed_query(self,text):
        return self.embed_documents([text])[0]


@pytest.fixture
def durable(tmp_path):
    pgserver = pytest.importorskip('pgserver')
    from fasteners import InterProcessLock
    # Keep the disposable server's bookkeeping within the test directory.
    runtime=Path(tempfile.mkdtemp(prefix='finrag-socket-',dir='/tmp'))
    pgserver.PostgresServer.runtime_path = runtime
    pgserver.PostgresServer.lock_path = runtime/'lock'
    pgserver.PostgresServer._lock = InterProcessLock(str(pgserver.PostgresServer.lock_path))
    server = pgserver.get_server(tmp_path/'pg',cleanup_mode='stop')
    svc = PersistentRAGService(server.get_uri(),owner='alice',objects=LocalObjects(tmp_path/'objects'),
                               embeddings=Embeddings(),embedding_model='offline',dimensions=3,
                               cache_root=tmp_path/'cache',index_dir=tmp_path/'index')
    svc.registry.migrate()
    yield svc,server,tmp_path
    server._cleanup()
    shutil.rmtree(runtime)


def test_atomic_lifecycle_isolation_and_retries(durable):
    svc,server,root = durable
    req={'kind':'markdown','title':'Same title','request_key':'A',
         'metadata':{'company_id':'TEST','review_status':'confirmed','fiscal_year':2026,'fiscal_quarter':1}}
    a=svc.register(**req)
    assert svc.register(**req)['source_id']==a['source_id']
    svc.registry.update_metadata('alice',a['source_id'],{**a['metadata'],'company_name':'Test Incorporated'})
    assert svc.register(**req)['metadata']['company_name']=='Test Incorporated'
    with pytest.raises(ValueError):
        svc.register(**{**req,'title':'Different'})
    b=svc.register(kind='text',title='Same title')
    other=svc.registry.register('bob',{'kind':'text','title':'Other'})
    with pytest.raises(LookupError):
        svc.registry.get('alice',other['source_id'])
    first=b'# Q1 earnings\n\nRevenue was $42 million.\nCash was $8 million.\n'
    queued=svc.submit(a['source_id'],first)
    job=queued['job']['job_id']
    with ThreadPoolExecutor(2) as pool:
        claims=list(pool.map(lambda _:svc.registry.claim('alice',job),range(2)))
    assert sum(c is not None for c in claims)==1
    token=next(c['lease_token'] for c in claims if c)
    svc.registry.fail('alice',job,token,'retry',{})
    svc.process_job(job)
    svc.ingest_bytes(b['source_id'],b'Cash reserves total $12 million. Form 10-K ticker TEST00001.')
    with svc.registry.connect() as db:
        identifiers=db.execute("SELECT payload FROM chunks WHERE lexical @@ to_tsquery('simple','10 | k | test00001') AND parent_id IS NOT NULL").fetchall()
    assert any('TEST00001' in row['payload']['text'] for row in identifiers)
    assert PostgresRetriever(svc.registry,'alice',svc.embeddings,'offline',3,
                             {'source_id':str(b['source_id'])},lexical='postgres').retrieve('Form 10-K TEST00001')
    assert svc.status().n_children>=2
    current=svc.registry.get('alice',a['source_id'])
    assert svc.ingest_bytes(a['source_id'],first)['reused']
    newer=svc.submit(a['source_id'],b'# Q2\n\nRevenue is $50 million.')
    old_embed=svc.embeddings
    class Broken(Embeddings):
        def embed_documents(self,texts):
            raise RuntimeError('synthetic failure')
    svc.embeddings=Broken()
    with pytest.raises(RuntimeError):
        svc.process_job(newer['job']['job_id'])
    assert svc.registry.get('alice',a['source_id'])['active_build_id']==current['active_build_id']
    svc.embeddings=old_embed
    retriever=PostgresRetriever(svc.registry,'alice',old_embed,'offline',3,{'company_id':'TEST'})
    detail=retriever.retrieve_with_candidates('Revenue',k=8)
    assert detail['chunks'] and all(c.document_id==str(a['source_id']) for c in detail['chunks'])
    span=next(s for c in detail['chunks'] for s in c.evidence_spans if 'Revenue' in s.text)
    assert span.line_start==3 and span.heading_path==['Q1 earnings']
    assert PostgresRetriever(svc.registry,'bob',old_embed,'offline',3).retrieve('Revenue')==[]
    with pytest.raises(ValueError,match='profile'):
        PostgresRetriever(svc.registry,'alice',old_embed,'incompatible',3).retrieve('Revenue')
    svc.process_job(newer['job']['job_id'])
    assert svc.registry.get('alice',a['source_id'])['active_build_id']!=current['active_build_id']
    assert svc.registry.get('alice',a['source_id'])['metadata']['review_status']=='needs_review'
    assert retriever.retrieve('Revenue')==[]
    old=PostgresRetriever(svc.registry,'alice',old_embed,'offline',3,
                          {'source_id':str(a['source_id']),'version_id':str(current['active_version_id'])}).retrieve('Revenue')
    assert any('$42' in c.text for c in old)
    svc.registry.archive('alice',a['source_id'])
    assert len(svc.registry.list('alice'))==1
    assert retriever.retrieve('Revenue')==[]
    assert svc.objects.get(queued['version']['object_key'])==first

    # A late worker cannot activate an older request or silently reuse a stale lease.
    slow=svc.submit(b['source_id'],b'Cash reserves were $20 million.')
    fast=svc.submit(b['source_id'],b'Cash reserves are $25 million.')
    assert not svc.process_job(slow['job']['job_id'])['activated']
    svc.process_job(fast['job']['job_id'])
    assert svc.registry.get('alice',b['source_id'])['active_version_id']==fast['version']['version_id']
    expired=svc.submit(b['source_id'],b'Cash $30 million.')
    old_claim=svc.registry.claim('alice',expired['job']['job_id'],lease_seconds=-1)
    new_claim=svc.registry.claim('alice',expired['job']['job_id'])
    svc.registry.fail('alice',expired['job']['job_id'],old_claim['lease_token'],'stale',{})
    assert svc.registry.job('alice',expired['job']['job_id'])['lease_token']==new_claim['lease_token']


def test_private_api_auth_and_upload(durable,monkeypatch):
    from fastapi.testclient import TestClient
    from src.api.private_server import build_private_app
    svc,_,_=durable
    monkeypatch.setenv('OPENAI_API_KEY','offline-test-key')
    token='a-secure-test-token-of-32-characters'
    client=TestClient(build_private_app(svc,token))
    assert client.get('/sources').status_code==401
    client.headers['Authorization']='Bearer '+token
    assert client.post('/query',json={'question':'What is revenue?'}).json()['outcome']=='refuse'
    source=client.post('/sources',json={'kind':'text','title':'Note'}).json()
    result=client.post('/sources/'+source['source_id']+'/content',content=b'Revenue was $5 million.',headers={'Content-Type':'text/plain'})
    assert result.status_code==200,result.text
    svc.process_job(result.json()['job_id'])
    assert client.get('/health').json()['ready']
    assert client.post('/ingest',json={'path':'/etc/passwd'}).status_code==404
    assert client.patch('/sources/'+source['source_id']+'/metadata',json={'fiscal_quarter':9}).status_code==422


def test_backup_restore(durable):
    import subprocess
    import psycopg
    from pgserver._commands import POSTGRES_BIN_PATH
    svc,server,root=durable
    source=svc.register(kind='text',title='Restore')
    svc.ingest_bytes(source['source_id'],b'Revenue is $11 million.')
    dump=root/'backup.sql'
    subprocess.run([str(POSTGRES_BIN_PATH/'pg_dump'),server.get_uri(),'-f',str(dump)],check=True,capture_output=True)
    with psycopg.connect(server.get_uri(),autocommit=True) as db:
        db.execute('CREATE DATABASE restored')
    subprocess.run([str(POSTGRES_BIN_PATH/'psql'),server.get_uri(database='restored'),'-v','ON_ERROR_STOP=1','-f',str(dump)],check=True,capture_output=True)
    from src.storage.registry import Registry
    registry=Registry(server.get_uri(database='restored'))
    result=PostgresRetriever(registry,'alice',Embeddings(),'offline',3).retrieve('Revenue')
    assert len(result)==1 and '$11' in result[0].text
    version=registry.versions('alice',source['source_id'])[0]
    assert hashlib.sha256(svc.objects.get(version['object_key'])).hexdigest()==version['sha256']
