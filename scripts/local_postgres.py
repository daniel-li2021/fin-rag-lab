#!/usr/bin/env python3
"""Start/reuse a durable, socket-only development Postgres; never delete data."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def start(root=ROOT / 'index/product-local'):
    import pgserver
    import psycopg
    from fasteners import InterProcessLock
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    from src.storage.registry import Registry

    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    runtime = root / 'runtime'
    # macOS Unix socket paths are limited to 104 bytes, including the socket name.
    if len(os.fsencode(runtime)) > 75:
        runtime = Path('/tmp') / f'finrag-pg-{os.getuid()}-{hashlib.sha256(str(root).encode()).hexdigest()[:16]}'
    if runtime.is_symlink():
        raise ValueError('Local runtime directory cannot be a symlink')
    runtime.mkdir(exist_ok=True, mode=0o700)
    os.chmod(runtime, 0o700)
    pgserver.PostgresServer.runtime_path = runtime
    pgserver.PostgresServer.lock_path = runtime / 'lock'
    pgserver.PostgresServer._lock = InterProcessLock(str(runtime / 'lock'))
    server = pgserver.get_server(root / 'postgres', cleanup_mode=None)
    with psycopg.connect(server.get_uri(), autocommit=True) as db:
        db.execute('SELECT pg_advisory_lock(724902613)')
        if not db.execute("SELECT 1 FROM pg_roles WHERE rolname='finrag_app'").fetchone():
            db.execute('CREATE ROLE finrag_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE')
        if not db.execute("SELECT 1 FROM pg_database WHERE datname='finrag'").fetchone():
            db.execute('CREATE DATABASE finrag OWNER finrag_app')
    with psycopg.connect(server.get_uri(database='finrag'), autocommit=True) as db:
        db.execute('CREATE EXTENSION IF NOT EXISTS vector')
        if db.execute('SHOW listen_addresses').fetchone()[0]:
            raise RuntimeError('Development Postgres must listen only on its private Unix socket')
    params = conninfo_to_dict(server.get_uri(database='finrag'))
    params['user'] = 'finrag_app'
    dsn = make_conninfo(**params)
    Registry(dsn).migrate()
    profile = root / 'runtime.env'
    profile.write_text(f'DATABASE_URL="{dsn}"\nFINRAG_OWNER=authentic-development\n'
                       f'FINRAG_OBJECT_DIR="{root / "objects"}"\nFINRAG_ALLOW_TRACING=false\n')
    os.chmod(profile, 0o600)
    return server, dsn, profile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'status', 'stop'])
    parser.add_argument('--root', type=Path, default=ROOT / 'index/product-local')
    args = parser.parse_args()
    if args.action == 'status':
        import psycopg
        from dotenv import dotenv_values
        profile = args.root / 'runtime.env'
        if not profile.exists():
            print(json.dumps({'status': 'not-initialized'}))
            return
        try:
            with psycopg.connect(dotenv_values(profile)['DATABASE_URL'], connect_timeout=3) as db:
                row = db.execute('SELECT current_database(), current_user').fetchone()
                counts = db.execute('SELECT count(*) FROM sources').fetchone()[0]
            print(json.dumps({'status': 'running', 'database': row[0], 'role': row[1], 'sources': counts}))
        except psycopg.OperationalError:
            print(json.dumps({'status': 'stopped', 'data_retained': True}))
        return
    server, _, profile = start(args.root)
    if args.action == 'stop':
        server.cleanup_mode = 'stop'
        server._cleanup()
    print(json.dumps({'status': 'running' if args.action == 'start' else 'stopped',
                      'profile': str(profile), 'data_retained': True, 'network_listener': False}))


if __name__ == '__main__':
    main()
