#!/usr/bin/env python3
"""Bounded A–D retrieval-only screening; stop paid judging when recall cannot pass."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from src.services.persistent_service import PersistentRAGService
from src.core.models import Document,DocumentBlock,DocumentChunk
from src.evaluators.contextual import contextualize,representation,evidence_budget
from src.evaluators.benchmark import load_benchmark,manifest,score,summarize,serializable
from src.retrievers.bm25 import BM25Retriever
from src.retrievers.rrf import rrf_merge

METADATA={
 'wells_fargo':{'company_id':'wells_fargo','company_name':'Wells Fargo','period_label':'Q4 2025',
                'fiscal_year':2025,'fiscal_quarter':4,'document_type':'earnings_release','review_status':'confirmed'},
 'tesla':{'company_id':'tesla','company_name':'Tesla','period_label':'Q1 2026',
          'fiscal_year':2026,'fiscal_quarter':1,'document_type':'earnings_presentation','review_status':'confirmed'},
 'amd':{'company_id':'amd','company_name':'AMD','period_label':'Q4 and full year 2025',
        'fiscal_year':2025,'fiscal_quarter':4,'document_type':'earnings_presentation','review_status':'confirmed'},
}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--context-model',default='gpt-6-luna')
    p.add_argument('--arms',default='ABCD')
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    examples,overlay=load_benchmark(ROOT/'data/golden_set/golden.jsonl',ROOT/'data/golden_set/labels.v1.json')
    svc=PersistentRAGService(os.environ['DATABASE_URL'],owner='experiment',
                             index_dir=args.output,cache_root=ROOT/'cache')
    svc.registry.migrate()
    all_parents,all_children,contexts,metadata=[],[],{},{}
    documents=[]
    ingest_start=time.perf_counter()
    with svc.cost_tracker.request() as ingestion:
        for name,source in overlay['corpus'].items():
            data=(ROOT/source['path']).read_bytes()
            if hashlib.sha256(data).hexdigest()!=source['sha256']:
                raise ValueError('Corpus hash mismatch')
            registered=svc.register(kind='pdf',title=name,request_key=name,metadata=METADATA[name])
            receipt=svc.ingest_bytes(registered['source_id'],data)
            active=svc.registry.get(svc.owner,registered['source_id'])
            with svc.registry.connect() as db:
                blocks=[DocumentBlock.model_validate(r['payload']) for r in db.execute('SELECT payload FROM blocks WHERE build_id=%s ORDER BY payload->>\'page_number\',block_id',(active['active_build_id'],)).fetchall()]
                rows=db.execute('SELECT payload FROM chunks WHERE build_id=%s ORDER BY ordinal',(active['active_build_id'],)).fetchall()
            chunks=[DocumentChunk.model_validate(r['payload']) for r in rows]
            parents=[c for c in chunks if c.parent_chunk_id is None]
            children=[c for c in chunks if c.parent_chunk_id]
            doc=Document(document_id=str(registered['source_id']),title=name,source_type='pdf',source_hash=source['sha256'],blocks=blocks)
            documents.append((name,doc,children))
            all_parents.extend(parents);all_children.extend(children)
            for c in children:metadata[c.chunk_id]=METADATA[name]
            print(json.dumps({'source':name,'children':len(children),'reused':receipt['reused']}),flush=True)
        ingest_usage=ingestion.report()
    ingest_seconds=time.perf_counter()-ingest_start
    context_start=time.perf_counter()
    with svc.cost_tracker.request() as context_receipt:
        if any(a in args.arms for a in 'CD'):
            for name,doc,children in documents:
                contexts.update(contextualize(doc,children,args.output/'context_cache',svc.cost_tracker,args.context_model))
                print(json.dumps({'context_source':name,'prefixes':len(children)}),flush=True)
        context_usage=context_receipt.report()
    context_seconds=time.perf_counter()-context_start
    # Cached paid batches belong to ingestion overhead even after a resumed run.
    context_events=[event for path in (args.output/'context_cache').glob('*.json')
                    for event in json.loads(path.read_text())['usage']['events']]
    context_totals={'calls':len(context_events),
        'input_tokens':sum(e.get('input_tokens') or 0 for e in context_events),
        'output_tokens':sum(e.get('output_tokens') or 0 for e in context_events),
        'unknown_cost_calls':sum(e.get('cost_usd') is None for e in context_events),
        'cost_usd':sum(e['cost_usd'] for e in context_events) if all(e.get('cost_usd') is not None for e in context_events) else None}
    query_vectors=svc.embeddings.embed_documents([e['question'] for e in examples])
    import numpy as np
    parent_store={c.chunk_id:c for c in all_parents}
    output={}
    for arm in args.arms:
        start=time.perf_counter()
        children=[]
        for c in all_children:
            children.extend(representation([c],arm,metadata[c.chunk_id],contexts))
        with svc.cost_tracker.request() as embedding_receipt:
            vectors=svc.embeddings.embed_documents([c.retrieval_text or c.text for c in children])
            usage=embedding_receipt.report()
        matrix=np.array(vectors);matrix=matrix/np.linalg.norm(matrix,axis=1,keepdims=True)
        bm25=BM25Retriever();bm25.index(children)
        rows=[]
        for e,query_vector in zip(examples,query_vectors):
            t0=time.perf_counter()
            q=np.array(query_vector);q=q/np.linalg.norm(q)
            similarities=matrix@q
            ordered=sorted(range(len(children)),key=lambda i:(-similarities[i],children[i].chunk_id))[:20]
            vec=[(children[i],float(similarities[i])) for i in ordered]
            fused=rrf_merge([vec,bm25.search_with_scores(e['question'],20)],top_n=20)
            candidates=[c for c,_ in fused]
            targets=candidates if arm=='D' else list({c.parent_chunk_id:parent_store[c.parent_chunk_id] for c in candidates}.values())
            final=evidence_budget(targets,2400)
            result=serializable({'chunks':final,'candidates':candidates,'retrieval_latency_ms':(time.perf_counter()-t0)*1000})
            rows.append({'id':e['id'],'question':e['question'],'category':e['category'],'label':e,
                         'result':result,'metrics':score(e,result)})
        (args.output/f'{arm}.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
        output[arm]={'summary':summarize(rows),'embedding_usage':usage,'embedding_seconds':time.perf_counter()-start}
        print(json.dumps({'arm':arm,'recall':output[arm]['summary']['all']['metrics']['evidence_recall_final']}),flush=True)
    reference=output['A']['summary']['all']['metrics']['evidence_recall_final']['mean']
    deltas={a:output[a]['summary']['all']['metrics']['evidence_recall_final']['mean']-reference for a in output if a!='A'}
    rows_by_arm={a:[json.loads(line) for line in (args.output/f'{a}.jsonl').read_text().splitlines()] for a in output}
    paired={a:[{'id':x['id'],'recall_delta':y['metrics']['evidence_recall_final']-x['metrics']['evidence_recall_final']
                if x['metrics']['evidence_recall_final'] is not None else None}
                for x,y in zip(rows_by_arm['A'],rows_by_arm[a])] for a in deltas}
    report={'decision':'retain_parent_child','promotion_status':'inconclusive' if any(d>=.10 for d in deltas.values()) else 'recall_gate_failed',
        'reason':'Promotion also requires reviewed numeric/outcome/citation/faithfulness/cost results; retrieval alone cannot promote.',
        'macro_recall_deltas':deltas,'paired_deltas':paired,'arms':output,'ingestion_usage':ingest_usage,
        'ingestion_seconds':ingest_seconds,'context_usage':context_usage,'all_cached_context_usage':context_totals,'context_seconds':context_seconds,
        'abstained_prefixes':sum(not c for c in contexts.values()),'n_children':len(all_children),'token_budget':2400,
        'run_manifest':manifest(ROOT,ROOT/'data/golden_set/golden.jsonl',ROOT/'data/golden_set/labels.v1.json',
            {'arms':args.arms,'embedding_model':svc.embedding_model,'dimensions':svc.dimensions,'context_model':args.context_model,
             'context_prompt_revision':1,'context_block_order':'page_string_then_block_id',
             'evidence_budget':2400,'fetch_k':20,'rrf_k':60,'source_metadata':METADATA},overlay['corpus'])}
    (args.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'decision':report['decision'],'deltas':deltas}),flush=True)


if __name__=='__main__':
    main()
