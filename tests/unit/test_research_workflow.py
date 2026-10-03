"""Sequential templates and original candidates obey coverage and bounded execution."""
from datetime import date

from src.core.models import DocumentBlock
from src.financial.intent import resolve_question
from src.financial.evidence import EvidenceSearchRequest, search_evidence
from src.financial.models import PinnedSource
from src.pipelines.query import QueryPipeline
from tests.unit.test_financial_research import fact, plan, snapshot, SOURCE_ID


def test_templates_keep_company_period_scope_and_basis_explicit():
    observation, block = fact()
    inventory = [{'source_id': SOURCE_ID, 'metadata': {'company_id': 'TEST', 'company_name': 'Test', 'review_status': 'confirmed'}}]
    selections = [{'source_id': SOURCE_ID}]
    resolution = resolve_question('show GAAP consolidated revenue for Test in Q1 2026', selections, inventory, [observation])
    assert resolution['request']['tasks'][0]['period']['end'] == '2026-03-31'
    assert resolve_question('What was Test gross margin?', selections, inventory, [observation])['outcome'] == 'clarify'
    assert resolve_question('compare GAAP consolidated revenue for Test and Missing in Q1 2026', selections, inventory, [observation])['outcome'] == 'refuse'
    request = resolve_question('show GAAP consolidated revenue for Test in Q2 2026', selections, inventory, [observation])['request']
    assert request['tasks'][0]['period']['calendar'] == 'unresolved'
    pipeline = QueryPipeline(None, None)
    result = pipeline.research({**resolution['request'], 'observations': [observation.model_dump(mode='json')]}, snapshot([observation], [block]))
    assert result['outcome'] == 'answer' and result['usage']['generator_calls'] == 0


def test_company_task_search_preserves_both_original_sources_and_budget():
    pin_a = PinnedSource(source_id=SOURCE_ID, version_id='version-a', build_id='build-a', source_hash='a' * 64,
                         company_id='A', publication_date=date(2026, 4, 10))
    pin_b = pin_a.model_copy(update={'source_id': 'source-b', 'version_id': 'version-b', 'build_id': 'build-b',
                                   'source_hash': 'b' * 64, 'company_id': 'B'})
    a = DocumentBlock(block_id='a', block_type='paragraph', text='Credit risk and credit losses.',
                      semantic_content='Generated AI revenue was 900 billion.', page_number=1)
    b = DocumentBlock(block_id='b', block_type='paragraph', text='Supply risk and export controls.', page_number=2)
    snap = {'sources': [pin_a, pin_b], 'blocks': {'build-a': [a], 'build-b': [b]},
            'inventory': [{'source_id': p.source_id, 'metadata': {'company_id': p.company_id, 'period_label': 'Q1 2026'}} for p in (pin_a, pin_b)]}
    request = EvidenceSearchRequest(question='Review risk disclosures', selections=[{'source_id': SOURCE_ID}],
        tasks=[{'task_id': 'a', 'company_id': 'A', 'query': 'risk'}, {'task_id': 'b', 'company_id': 'B', 'query': 'risk'}])
    result = QueryPipeline(None, None).evidence(request, snap)
    assert {p['source']['company_id'] for p in result['passages']} == {'A', 'B'}
    assert result['original_tokens'] <= 6000 and all(n <= 2 for n in result['attempts'].values())
    assert all('Generated' not in p['text'] for p in result['passages'])
    assert result['outcome'] == 'qualified_answer'
    assert all(c['status'] == 'binding_unverified' for c in result['coverage'])
    repaired = search_evidence(request.model_copy(update={'tasks': (request.tasks[0].model_copy(
        update={'query': 'nonexistent', 'repair_query': 'credit'}),)}), snap)
    assert repaired['attempts']['a'] == 2 and repaired['passages']
    huge = a.model_copy(update={'text': 'risk ' * 20000})
    blocked = search_evidence(request, {**snap, 'blocks': {'build-a': [huge], 'build-b': [b]}})
    assert blocked['original_tokens'] <= 6000
    assert blocked['coverage'][0]['status'] == 'passage_not_found' and blocked['coverage'][0]['budget_exhausted']
    future = search_evidence(request.model_copy(update={'as_of': date(2026, 4, 1)}), snap)
    assert not future['passages'] and future['outcome'] == 'refuse'
    missing_date = search_evidence(request.model_copy(update={'as_of': date(2026, 4, 1)}),
        {**snap, 'sources': [pin_a.model_copy(update={'publication_date': None}), pin_b]})
    assert missing_date['outcome'] == 'clarify' and not missing_date['passages']
    punctuation = search_evidence(request, {**snap, 'blocks': {'build-a': [a.model_copy(update={'text': '---'})]}})
    assert not punctuation['passages']
    zero_table = DocumentBlock(block_id='zero', block_type='table', structured_data={'rows': [['risk losses', 0, None]]})
    assert zero_table.get_original_text() == 'risk losses | 0 | '
    zero = search_evidence(request, {**snap, 'blocks': {'build-a': [zero_table]}})
    assert zero['passages'][0]['text'] == 'risk losses | 0 | '
