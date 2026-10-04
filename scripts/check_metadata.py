#!/usr/bin/env python3
"""Six synthetic labeled sources, one cached Luna suggestion call per unresolved version."""
import json
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from src.services.persistent_service import PersistentRAGService
from src.pipelines.metadata import suggest_metadata

CASES=[
 ('Acme Holdings reports fiscal Q1 2026 earnings. This earnings release announces revenue of $42 million.',
  ['Acme Holdings',2026,1,'earnings_release']),
 ('Beta Robotics fiscal Q4 2025 Earnings Presentation. These slides present quarterly results for shareholders.',
  ['Beta Robotics',2025,4,'earnings_presentation']),
 ('Cedar Inc. fiscal Q2 2026 earnings call transcript. Operator: welcome to the quarterly earnings call.',
  ['Cedar Inc.',2026,2,'transcript']),
 ('Internal analyst note about the weather. Published January 4, 2026. No company or fiscal reporting period is identified.',
  [None,None,None,'note']),
 ('Aster Ltd. Form 10-Q for fiscal Q3 2025. This quarterly filing contains the financial statements.',
  ['Aster Ltd.',2025,3,'10-Q']),
 ('Companies Acme and Beta are discussed as examples; neither is the issuer. Publication date 2026-04-01. Document type is unknown.',
  [None,None,None,None]),
]


def main():
    class Embeddings:
        def embed_documents(self,texts):return [[1.,0.,0.] for _ in texts]
        def embed_query(self,text):return [1.,0.,0.]
    svc=PersistentRAGService(os.environ['DATABASE_URL'],owner='metadata-check',embedding_model='synthetic',dimensions=3,embeddings=Embeddings(),index_dir=ROOT/'index/metadata-check')
    svc.registry.migrate()
    rows=[]
    with svc.cost_tracker.request() as receipt:
        for number,(text,expected) in enumerate(CASES,1):
            source=svc.register(kind='text',title=f'Synthetic {number}',request_key=str(number))
            svc.ingest_bytes(source['source_id'],text.encode())
            result=suggest_metadata(svc,source['source_id'])
            values={s['field']:s['value'] for s in result['suggestions']}
            fields=['company_name','fiscal_year','fiscal_quarter','document_type']
            actual=[values[f] for f in fields]
            assert suggest_metadata(svc,source['source_id'])['reused']
            rows.append({'case':number,'expected':dict(zip(fields,expected)),'actual':values,
                         'correct_fields':sum(a==b for a,b in zip(actual,expected)),
                         'abstentions':sum(v is None for v in actual),'evidence_validated':True})
            print(json.dumps(rows[-1]),flush=True)
        usage=receipt.report()
    report={'cases':rows,'correct_fields':sum(r['correct_fields'] for r in rows),'field_denominator':len(rows)*4,
            'abstentions':sum(r['abstentions'] for r in rows),'usage':usage,'model':'gpt-6-luna',
            'synthetic_only':True,'decision':'suggestions_require_user_confirmation'}
    destination = ROOT/'docs/evidence/checks/METADATA_CHECK.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    main()
