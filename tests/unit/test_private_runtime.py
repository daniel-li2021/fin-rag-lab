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
