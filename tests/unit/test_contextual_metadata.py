import pytest
from src.core.models import Document,DocumentBlock
from src.chunkers import ParentChildChunker
from src.chunkers._token_utils import get_token_counter
from src.evaluators.contextual import evidence_budget,representation
from src.pipelines.metadata import validate_suggestions,explicit_suggestions
from src.storage.migration import ReusedEmbeddings,trusted_vectors


def test_budget_preserves_offsets_and_deduplicates():
    block=DocumentBlock(block_type='paragraph',text='Revenue was 42. '*100,line_start=3,page_number=1)
    doc=Document(title='Report',source_type='text',source_hash='a'*64,blocks=[block])
    parents,children=ParentChildChunker(parent_size=80,child_size=40,parent_overlap=20,child_overlap=10).chunk_with_parents(doc)
    selected=evidence_budget(parents,100)
    count=get_token_counter('gpt-4o')
    assert count('\n\n'.join(c.text for c in selected))<=100
    occupied=set()
    for c in selected:
        for s in c.evidence_spans:
            assert s.text==block.text[s.char_start:s.char_end]
            locations=set(range(s.char_start,s.char_end))
            assert not occupied&locations
            occupied|=locations
    a=representation(children,'A')
    b=representation(children,'B',{'company_name':'Acme','period_label':'Q1 2026'})
    c=representation(children,'C',contexts={c.chunk_id:'context' for c in children})
    assert a[0].text==b[0].text==c[0].text
    assert a[0].evidence_spans==c[0].evidence_spans
    assert b[0].retrieval_text.startswith('Acme')


def test_suggestions_require_evidence_and_valid_fields():
    block=DocumentBlock(block_type='paragraph',text='Acme fiscal Q1 2026')
    payload={'suggestions':[{'field':'fiscal_quarter','value':1,'block_id':block.block_id,'quote':'Q1 2026'}]}
    result=validate_suggestions(payload,['fiscal_quarter'],[block])
    assert result['review_status']=='needs_review' and result['suggestions'][0]['char_start']==12
    payload['suggestions'][0]['quote']='made up'
    with pytest.raises(ValueError):validate_suggestions(payload,['fiscal_quarter'],[block])
    front=DocumentBlock(block_type='paragraph',text='---\ncompany_name: Acme\nfiscal_year: 2026\nfiscal_quarter: 1\ndocument_type: note\n---')
    suggestions=explicit_suggestions([front],['company_name','fiscal_year','fiscal_quarter','document_type'])
    assert len(suggestions)==4
    conflict=DocumentBlock(block_type='paragraph',text='fiscal_year: 2025')
    assert not explicit_suggestions([front,conflict],['fiscal_year'])
    payload['suggestions'][0].update(quote='Q1 2026',value=9)
    with pytest.raises(ValueError):validate_suggestions(payload,['fiscal_quarter'],[block])


def test_migration_reuses_only_proven_inputs(tmp_path):
    import json
    (tmp_path/'index_meta.json').write_text(json.dumps({'embedding_model':None}))
    with pytest.raises(ValueError,match='unverifiable'):trusted_vectors(tmp_path,'offline',3)
    class Fallback:
        def embed_documents(self,texts):
            assert texts==['new'];return [[2.]]
    adapter=ReusedEmbeddings({'known':[1.]},Fallback())
    assert adapter.embed_documents(['known','new','new'])==[[1.],[2.],[2.]]
