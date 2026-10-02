#!/usr/bin/env python3
"""Same vectors, source filters, fusion and token budget; compare BM25 with SQL ranking."""
import json
import os
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from src.services.persistent_service import PersistentRAGService
from src.retrievers.postgres import PostgresRetriever
from src.evaluators.contextual import evidence_budget
from src.evaluators.benchmark import load_benchmark,score,serializable,latency_summary


def main():
    examples,_=load_benchmark(ROOT/'data/golden_set/golden.jsonl',ROOT/'data/golden_set/labels.v1.json')
    svc=PersistentRAGService(os.environ['DATABASE_URL'],owner='experiment',index_dir=ROOT/'index/experiment-20261002')
    with svc.cost_tracker.request() as receipt:
        vectors=svc.embeddings.embed_documents([e['question'] for e in examples])
        query_usage=receipt.report()
    mapping=dict(zip((e['question'] for e in examples),vectors))
    class QueryVectors:
        def embed_query(self,text):return mapping[text]
    rows=[]
    for e in examples:
        row={'id':e['id'],'question':e['question'],'branches':{}}
        for lexical in ('bm25','postgres'):
            retriever=PostgresRetriever(svc.registry,svc.owner,QueryVectors(),svc.embedding_model,svc.dimensions,lexical=lexical)
            t0=time.perf_counter();result=retriever.retrieve_with_candidates(e['question'],k=20)
            result['chunks']=evidence_budget(result['chunks'],2400)
            latency=(time.perf_counter()-t0)*1000
            metric=score(e,serializable(result))
            row['branches'][lexical]={'final_recall':metric['evidence_recall_final'],
                'latency_ms':latency,'candidate_ids':[c.chunk_id for c in result['candidates']],
                'source_versions':sorted({c.source_version for c in result['chunks']})}
        rows.append(row)
    summary={}
    for lexical in ('bm25','postgres'):
        values=[r['branches'][lexical]['final_recall'] for r in rows if r['branches'][lexical]['final_recall'] is not None]
        summary[lexical]={'macro_recall':sum(values)/len(values),'denominator':len(values),
                          'latency_ms':latency_summary([r['branches'][lexical]['latency_ms'] for r in rows])}
    pairs=[{'id':r['id'],'recall_delta':r['branches']['postgres']['final_recall']-r['branches']['bm25']['final_recall']
            if r['branches']['bm25']['final_recall'] is not None else None,
            'ranking_changed':r['branches']['postgres']['candidate_ids']!=r['branches']['bm25']['candidate_ids']} for r in rows]
    # Compare actual pgvector RRF candidates with the saved exact local cosine control.
    reference=ROOT/'index/experiment-20261002/A.jsonl'
    parity=None
    if reference.exists():
        a=[json.loads(line) for line in reference.read_text().splitlines()]
        matches=sum(r['branches']['bm25']['candidate_ids']==[c['chunk_id'] for c in x['result']['candidates']] for r,x in zip(rows,a))
        parity={'identical_rankings':matches,'denominator':len(a),'distance':'cosine',
                'note':'Exact local reference uses the same input vectors; float32 rounding/ties are recorded as differences.'}
    report={'decision':'retain_bm25','reason':'Retrieval screening does not establish answer/refusal parity. SQL lexical ranking remains opt-in.',
            'summary':summary,'paired_deltas':pairs,'vector_reference_parity':parity,'query_embedding_usage':query_usage,
            'token_budget':2400,'fetch_k':20,'rrf_k':60,'questions':rows}
    (ROOT/'docs/LEXICAL_CHECK.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'summary':summary,'parity':parity,'decision':report['decision']}),flush=True)


if __name__=='__main__':
    main()
