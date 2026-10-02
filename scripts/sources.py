#!/usr/bin/env python3
"""Register, ingest, query, or process one durable job. No deployment side effects."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from src.services.persistent_service import PersistentRAGService


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['migrate','list','register','ingest','snapshot','worker','query','archive'])
    p.add_argument('--source-id')
    p.add_argument('--job-id')
    p.add_argument('--kind',choices=['pdf','text','markdown','url'])
    p.add_argument('--title')
    p.add_argument('--locator')
    p.add_argument('--request-key')
    p.add_argument('--file',type=Path)
    p.add_argument('--question')
    p.add_argument('--filters',default='{}')
    p.add_argument('--metadata',default='{}')
    args = p.parse_args()
    svc = PersistentRAGService(os.environ['DATABASE_URL'],owner=os.getenv('FINRAG_OWNER','default'))
    if args.action=='migrate':
        svc.registry.migrate(); result={'status':'migrated'}
    elif args.action=='list':
        result=svc.registry.list(svc.owner)
    elif args.action=='register':
        result=svc.register(kind=args.kind,title=args.title,locator=args.locator,request_key=args.request_key,metadata=json.loads(args.metadata))
    elif args.action=='ingest':
        if not args.file or not args.source_id:
            p.error('ingest requires --file and --source-id')
        result=svc.ingest_bytes(args.source_id,args.file.read_bytes())
    elif args.action=='snapshot':
        job=svc.snapshot(args.source_id); result=svc.process_job(job['job']['job_id'])
    elif args.action=='worker':
        if args.job_id:
            result=svc.process_job(args.job_id)
        else:
            with svc.registry.connect() as db:
                job=db.execute('''SELECT j.job_id FROM ingestion_jobs j JOIN retrieval_builds b USING(build_id)
                    JOIN source_versions v USING(version_id) JOIN sources s USING(source_id)
                    WHERE s.owner_id=%s AND s.status<>'archived' AND
                    (j.status='pending' OR (j.status='processing' AND j.lease_until<now())) ORDER BY j.created_at LIMIT 1''',(svc.owner,)).fetchone()
            result=svc.process_job(job['job_id']) if job else {'status':'idle'}
    elif args.action=='archive':
        result=svc.registry.archive(svc.owner,args.source_id)
    else:
        result=svc.query(args.question,filters=json.loads(args.filters)).to_display_dict()
    from fastapi.encoders import jsonable_encoder
    print(json.dumps(jsonable_encoder(result),indent=2))


if __name__=='__main__':
    main()
