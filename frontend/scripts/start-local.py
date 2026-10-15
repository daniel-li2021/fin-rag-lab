"""Run the existing private FastAPI against the retained local development corpus."""
import os
from pathlib import Path
import sys
from dotenv import dotenv_values, load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / '.env')
for key, value in dotenv_values(ROOT / 'index/product-local/runtime.env').items():
    os.environ[key] = value
# Share a server-only local token. It is never printed or passed to the browser.
port = int(os.getenv('FINRAG_LOCAL_PORT', '8010'))
profile = ROOT / 'frontend/.env.local'
config = dotenv_values(profile)
if not config.get('FINRAG_API_TOKEN'):
    import secrets
    profile.write_text(f'FINRAG_BACKEND_URL=http://127.0.0.1:{port}\nFINRAG_API_TOKEN=' + secrets.token_urlsafe(36) + '\n')
    profile.chmod(0o600)
    config = dotenv_values(profile)
os.environ['FINRAG_API_TOKEN'] = config['FINRAG_API_TOKEN']
from src.api.private_server import build_private_app
import uvicorn
uvicorn.run(build_private_app(), host='127.0.0.1', port=port, access_log=False)
