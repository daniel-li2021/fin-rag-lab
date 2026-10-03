"""Offline synthetic checks of issued operands, coverage and deterministic exports."""
from datetime import date
from decimal import Decimal

import pytest

from src.core.models import DocumentBlock
from src.financial.models import FinancialObservation, FinancialPeriod, PinnedSource, EvidenceLink, CoverageTask
from src.financial.calculations import CalculationRequest, calculate
from src.financial.research import ResearchRequest, run_research


SOURCE_ID = '00000000-0000-0000-0000-000000000001'
VERSION_ID = '00000000-0000-0000-0000-000000000002'
BUILD_ID = '00000000-0000-0000-0000-000000000003'


def fact(value='12', metric='revenue', unit='currency', scale='1000000', company='TEST',
         period=None, source=None, observation_id='revenue', scope='consolidated'):
    period = period or FinancialPeriod(kind='quarter', start=date(2026, 1, 1), end=date(2026, 3, 31), fiscal_label='Q1 2026')
    source = source or PinnedSource(source_id=SOURCE_ID, version_id=VERSION_ID, build_id=BUILD_ID,
        source_hash='a' * 64, company_id=company, publication_date=date(2026, 4, 10))
    labels = {'row_label': metric, 'column_period': period.fiscal_label,
              'unit': ('USD millions' if scale == '1000000' else 'USD') if unit == 'currency' else
                      'percent' if unit == 'percent' else 'vehicles',
              'basis': 'GAAP', 'scope': scope, 'value': value}
    text = ' | '.join(labels.values())
    block = DocumentBlock(block_id='block-' + observation_id, block_type='paragraph', text=text, page_number=1)
    evidence = tuple(EvidenceLink(role=role, block_id=block.block_id, text=label,
        char_start=text.index(label), char_end=text.index(label) + len(label), page_number=1)
        for role, label in labels.items())
    observation = FinancialObservation(observation_id=observation_id, company_id=company, metric_id=metric,
        original_label=metric, value=value, unit=unit, scale=scale, currency='USD' if unit == 'currency' else None,
        period=period, source=source, scope=scope, evidence=evidence, verification_status='reviewed', review_revision='synthetic-review-v1')
    return observation, block


def plan(observations, *, calculations=(), mode='lookup', tasks=None, as_of=None):
    return ResearchRequest(question='Synthetic offline check', selections=({'source_id': SOURCE_ID},),
        tasks=tasks or tuple(CoverageTask(task_id=o.observation_id, company_id=o.company_id, metric_id=o.metric_id,
                                          period=o.period, scope=o.scope, basis=o.basis) for o in observations),
        observations=observations, calculations=calculations, mode=mode, as_of=as_of)


def snapshot(observations, blocks):
    return {'sources': list({o.source.build_id: o.source for o in observations}.values()),
        'blocks': {observations[0].source.build_id: blocks},
        'inventory': [{'source_id': SOURCE_ID, 'metadata': {'company_id': 'TEST', 'review_status': 'confirmed'}}]}


def test_receipt_normalizes_scale_and_keeps_all_operand_citations():
    a, _ = fact('3', metric='gross_profit', observation_id='profit')
    b, _ = fact('12', observation_id='revenue')
    receipt = calculate(CalculationRequest(operation='margin', start_task_id='profit', end_task_id='revenue'), a, b)
    assert receipt.normalized_operands == ('3000000', '12000000')
    assert Decimal(receipt.result) == 25 and receipt.displayed_result == '25.00%'
    assert receipt.observation_ids == ('profit', 'revenue')
    assert all(len(c['evidence']) == 6 for c in receipt.citations)
    with pytest.raises(ValueError, match='denominator'):
        calculate(CalculationRequest(operation='margin', start_task_id='profit', end_task_id='zero'),
                  a, b.model_copy(update={'value': '0'}))
    with pytest.raises(ValueError, match='metrics'):
        calculate(CalculationRequest(operation='difference', start_task_id='profit', end_task_id='revenue'), a, b)


def test_percentage_points_and_duration_policy_are_explicit():
    period = FinancialPeriod(kind='quarter', start=date(2025, 10, 1), end=date(2025, 12, 31), fiscal_label='Q4 2025')
    previous = period.model_copy(update={'start': date(2024, 10, 1), 'end': date(2024, 12, 31), 'fiscal_label': 'Q4 2024'})
    a, _ = fact('51', metric='gross_margin', unit='percent', scale='1', period=previous, observation_id='old')
    b, _ = fact('54', metric='gross_margin', unit='percent', scale='1', period=period, observation_id='new')
    req = CalculationRequest(operation='percentage_point_change', start_task_id='old', end_task_id='new')
    assert calculate(req, a, b).displayed_result == '+3.00 percentage points'
    with pytest.raises(ValueError, match='percentage_point_change'):
        calculate(req.model_copy(update={'operation': 'difference'}), a, b)
    later = b.model_copy(update={'period': period.model_copy(update={'start': date(2025, 10, 2)})})
    with pytest.raises(ValueError, match='durations'):
        calculate(req, a, later)
    assert calculate(req.model_copy(update={'period_policy': 'reporting_kind'}), a, later).limitations
    with pytest.raises(ValueError, match='positive baseline'):
        calculate(req.model_copy(update={'operation': 'growth'}), a.model_copy(update={'value': '-1'}), b)


def test_research_requires_every_rank_candidate_and_exports_reproducible_trace():
    a, block = fact()
    missing = CoverageTask(task_id='missing', company_id='OTHER', metric_id='revenue', period=a.period)
    req = plan((a,), tasks=(CoverageTask(task_id='revenue', company_id='TEST', metric_id='revenue', period=a.period), missing), mode='ranking')
    snap = snapshot([a], [block])
    result = run_research(req, snap)
    assert result['outcome'] == 'qualified_answer' and result['ranking'] == []
    assert result['coverage'][1]['status'] == 'source_absent'
    assert result['calculations'] == [] and result['citations']['revenue']['evidence']
    assert result == run_research(req, snap)
    assert result['usage'] == {'planner_calls': 0, 'generator_calls': 0, 'embedding_calls': 0, 'cost_usd': '0'}
    forged = a.model_copy(update={'value': '13'})
    invalid = run_research(plan((forged,)), snap)
    assert invalid['outcome'] == 'refuse' and invalid['coverage'][0]['status'] == 'binding_unverified'
    assert not invalid['citations']


def test_conflict_cutoff_and_bounds_cannot_produce_calculations():
    a, block_a = fact('12', observation_id='a')
    b, block_b = fact('13', observation_id='b')
    task = CoverageTask(task_id='revenue', company_id='TEST', metric_id='revenue', period=a.period)
    conflict = run_research(plan((a, b), tasks=(task,)), snapshot([a, b], [block_a, block_b]))
    assert conflict['coverage'][0]['status'] == 'conflicting' and conflict['outcome'] == 'refuse'
    before = run_research(plan((a,), as_of=date(2026, 4, 1)), snapshot([a], [block_a]))
    assert before['outcome'] == 'refuse' and before['citations'] == {}
    with pytest.raises(ValueError, match='reference'):
        plan((a,), calculations=(CalculationRequest(operation='growth', start_task_id='a', end_task_id='absent'),))


def test_ranking_preserves_thirty_digit_values_and_comparison_discloses_scope():
    a, block_a = fact('100000000000000000000000000001', scale='1', observation_id='a', scope='segment_a')
    b, block_b = fact('100000000000000000000000000002', scale='1', observation_id='z', scope='segment_z')
    req = plan((a, b), mode='ranking')
    snap = snapshot([a, b], [block_a, block_b])
    assert run_research(req, snap)['ranking'] == ['z', 'a']
    comparison = run_research(plan((a, b), mode='comparison'), snap)
    assert comparison['outcome'] == 'qualified_answer'
    assert comparison['calculation_gaps'][0]['operation'] == 'comparison'
