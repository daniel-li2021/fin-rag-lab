"""The local profile survives process exits/restarts without widening access."""
import subprocess
import sys
from pathlib import Path

import psycopg
import pytest
from dotenv import dotenv_values

from src.storage.registry import Registry


def test_local_profile_persists_across_processes_and_restart(tmp_path):
    pytest.importorskip('pgserver')
    script = Path(__file__).resolve().parents[2] / 'scripts/local_postgres.py'
    root = tmp_path / 'durable'
    def command(action):
        subprocess.run([sys.executable, str(script), action, '--root', str(root)],
                       check=True, capture_output=True, text=True, timeout=30)
    try:
        command('start')
        dsn = dotenv_values(root / 'runtime.env')['DATABASE_URL']
        registry = Registry(dsn)
        row = registry.register('development', {'kind': 'text', 'title': 'Persistent identity', 'request_key': 'one'})
        command('start')
        with psycopg.connect(dsn) as db:
            assert db.execute('SHOW listen_addresses').fetchone()[0] == ''
            assert db.execute('SELECT rolsuper,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname=current_user').fetchone() == (False, False, False)
        assert not registry.list('another-owner')
        command('stop')
        assert (root / 'postgres/PG_VERSION').exists()
        command('start')
        assert dotenv_values(root / 'runtime.env')['DATABASE_URL'] == dsn
        assert registry.list('development')[0]['source_id'] == row['source_id']
        assert (root.stat().st_mode & 0o777) == 0o700
    finally:
        if (root / 'runtime.env').exists():
            command('stop')
