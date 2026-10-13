"""The private API must start without optional notebook/vector/evaluation packages."""
from pathlib import Path
import subprocess
import sys


def test_private_factory_does_not_require_lab_dependencies():
    script = '''
import importlib.abc, os, sys, tempfile
from pathlib import Path
class NoLab(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'chromadb', 'langchain_chroma', 'streamlit', 'ragas', 'pandas', 'datasets', 'IPython', 'pgserver'}:
            raise ModuleNotFoundError(fullname)
sys.meta_path.insert(0, NoLab())
os.environ['OPENAI_API_KEY'] = 'offline-test-key'
from src.services.persistent_service import PersistentRAGService
from src.api.private_server import build_private_app
from src.storage.objects import LocalObjects
assert 'src.api.server' not in sys.modules
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    service = PersistentRAGService('postgresql://offline@localhost/unused',
        objects=LocalObjects(root/'objects'), index_dir=root/'index', cache_root=root/'cache')
    app = build_private_app(service, 'offline-token-at-least-24-characters')
    assert any(r.path == '/sources' for r in app.routes)
    assert not any(r.path == '/ingest' for r in app.routes)
'''
    subprocess.run([sys.executable, '-c', script], cwd=Path(__file__).resolve().parents[2],
                   check=True, capture_output=True, text=True)


def test_upload_owner_lookup_does_not_block_other_event_loop_work():
    import asyncio
    from threading import Event
    from uuid import UUID
    import httpx
    from src.api.private_server import build_private_app
    started, release = Event(), Event()
    class Registry:
        def get(self, owner, source_id):
            assert owner == 'test' and source_id == UUID(int=1)
            started.set()
            assert release.wait(timeout=2), 'Owner lookup blocked the ASGI event loop'
            return {}
    class Service:
        owner = 'test'
        registry = Registry()
        def submit(self, source_id, data, **kwargs):
            assert data == b'Original text'
            return {'job': {'job_id': UUID(int=2), 'status': 'pending'},
                    'version': {'version_id': UUID(int=3)}, 'build': {'build_id': UUID(int=4)}}
    async def check():
        async def other_work():
            while not started.is_set():
                await asyncio.sleep(.001)
            release.set()
        client_app = build_private_app(Service(), 'offline-token-at-least-24-characters')
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client_app), base_url='http://test') as client:
            response, _ = await asyncio.gather(client.post('/sources/' + str(UUID(int=1)) + '/content',
                content=b'Original text', headers={'Authorization': 'Bearer offline-token-at-least-24-characters',
                                                  'Content-Type': 'text/plain'}), other_work())
            assert response.status_code == 200 and response.json()['status'] == 'pending'
    asyncio.run(check())
