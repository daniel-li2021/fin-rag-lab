#!/usr/bin/env python3
"""Register legacy PDFs explicitly, preserving an old-document-ID migration map."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from src.services.persistent_service import PersistentRAGService
from src.storage.migration import trusted_vectors,ReusedEmbeddings


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--index-dir',type=Path,default=ROOT/'index')
    p.add_argument('--raw-dir',type=Path,default=ROOT/'data/uploads')
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.output.exists():
        p.error('Use a new migration-map file')
    meta=json.loads((args.index_dir/'index_meta.json').read_text())
    svc=PersistentRAGService(os.environ['DATABASE_URL'],owner=os.getenv('FINRAG_OWNER','default'))
    svc.registry.migrate()
    vector_status='verified_reuse'
    try:
        _,vectors=trusted_vectors(args.index_dir,svc.embedding_model,svc.dimensions)
        svc.embeddings=ReusedEmbeddings(vectors,svc.embeddings)
    except ValueError as exc:
        vector_status=str(exc)
    mapping=[]
    with svc.cost_tracker.request() as receipt:
        for doc in meta['documents']:
            name=Path(doc['source_path']).name
            path=args.raw_dir/name
            if not path.is_file():
                raise FileNotFoundError(f'Missing raw PDF: {name}')
            data=path.read_bytes()
            source=svc.register(kind='pdf',title=doc['title'],locator=name,request_key='legacy:'+doc['document_id'])
            svc.ingest_bytes(source['source_id'],data)
            active=svc.registry.get(svc.owner,source['source_id'])
            mapping.append({'legacy_document_id':doc['document_id'],'source_id':str(source['source_id']),
                            'source_version_id':str(active['active_version_id']),'sha256':hashlib.sha256(data).hexdigest()})
            args.output.write_text(json.dumps({'mapping':mapping,'vector_status':vector_status,'usage':receipt.report()},indent=2)+'\n')
    print(json.dumps({'sources_migrated':len(mapping),'vector_status':vector_status,'usage':receipt.report()},indent=2))


if __name__=='__main__':
    main()
