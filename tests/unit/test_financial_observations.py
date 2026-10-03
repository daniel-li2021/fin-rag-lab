"""Synthetic adversarial contract cases, not authentic filing quality evidence."""
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.core.models import DocumentBlock
from src.financial.models import (CoverageTask, EvidenceLink, FinancialObservation,
                                  FinancialPeriod, PinnedSource)
from src.financial.observations import parse_decimal, select_observations, validate_observation


def sample(value='1,200', scale='1000000'):
    source = PinnedSource(source_id='issuer-report', version_id='bytes-v1', build_id='parse-v1',
                          source_hash='a' * 64, company_id='issuer', publication_date=date(2026, 2, 1))
    period = FinancialPeriod(kind='annual', start=date(2025, 1, 1), end=date(2025, 12, 31),
                             fiscal_label='FY2025', calendar='calendar')
    rows = [['GAAP consolidated USD millions', 'FY2025'], ['Revenue', value]]
    block = DocumentBlock(block_id='table', block_type='table', page_number=2,
                          structured_data={'rows': rows}, semantic_content='Invented revenue 9,999')
    links = tuple(EvidenceLink(role=role, block_id='table', text=rows[row][column],
                               row_index=row, column_index=column, page_number=2)
                  for role, row, column in [('value', 1, 1), ('row_label', 1, 0),
                                            ('column_period', 0, 1), ('unit', 0, 0),
                                            ('basis', 0, 0), ('scope', 0, 0)])
    observation = FinancialObservation(observation_id='revenue-original', company_id='issuer',
                                       metric_id='revenue', original_label='Revenue',
                                       value=str(parse_decimal(value)), unit='currency', currency='USD',
                                       scale=scale, period=period, source=source, evidence=links,
                                       verification_status='reviewed', review_revision='manual-review-v1')
    task = CoverageTask(task_id='annual-revenue', company_id='issuer', metric_id='revenue', period=period)
    return source, block, observation, task


def changed(record, **updates):
    """Revalidate updates; model_copy deliberately bypasses Pydantic validation."""
    return type(record).model_validate({**record.model_dump(), **updates})


def test_original_binding_rejects_generated_wrong_cells_values_units_and_pins():
    source, block, observation, _ = sample()
    assert validate_observation(observation, [block], [source]) == observation
    with pytest.raises(ValueError, match='original locator'):
        bad_link = changed(observation.evidence[0], text='9,999')
        validate_observation(changed(observation, evidence=(bad_link, *observation.evidence[1:])), [block], [source])
    for update in ({'value': '1201'}, {'scale': '1'}, {'currency': 'EUR'}):
        with pytest.raises(ValueError):
            validate_observation(changed(observation, **update), [block], [source])
    with pytest.raises(ValueError, match='pinned manifest'):
        validate_observation(observation, [block], [changed(source, build_id='other-build')])
    with pytest.raises(ValueError, match='share an original row'):
        label = changed(observation.evidence[1], row_index=0, column_index=1, text='FY2025')
        validate_observation(changed(observation, original_label='FY2025',
                                     evidence=(observation.evidence[0], label, *observation.evidence[2:])), [block], [source])
    generated = DocumentBlock(block_id='table', block_type='table', semantic_content=block.get_original_text())
    with pytest.raises(ValueError):
        validate_observation(observation, [generated], [source])


def test_original_whitespace_and_zero_cells_survive_validation():
    source, block, observation, _ = sample(value='0')
    block.structured_data['rows'][1][1] = 0
    assert validate_observation(observation, [block], [source]).value == '0'
    paragraph = DocumentBlock(block_id='span', block_type='paragraph', text=' 0 ', page_number=2)
    link = EvidenceLink(role='value', block_id='span', text=' 0 ', char_start=0, char_end=3)
    assert link.text == ' 0 '
    assert validate_observation(changed(observation, evidence=(link, *observation.evidence[1:])),
                                [block, paragraph], [source]).value == '0'


@pytest.mark.parametrize('raw,expected', [('$ 1,200', '1200'), ('(USD 1,200.50)', '-1200.50'),
                                          ('51%', '51'), ('−5', '-5'), ('0', '0')])
def test_original_decimal_parser(raw, expected):
    assert parse_decimal(raw) == Decimal(expected)


@pytest.mark.parametrize('raw', ['', '-', '—', 'N/A', 'NaN', 'Infinity', '1,20', 'Revenue 1200', '(+1)', '1e8'])
def test_missing_or_unbounded_original_values_never_become_numbers(raw):
    with pytest.raises(ValueError):
        parse_decimal(raw)


def test_review_contract_and_unresolved_periods_fail_closed():
    _, _, observation, _ = sample()
    for update in ({'value': 1200.0}, {'value': 'NaN'}, {'value': '1e100'}, {'review_revision': None},
                   {'scope': ' '}, {'evidence': observation.evidence[:2]}, {'unexpected': True}):
        with pytest.raises(ValidationError):
            changed(observation, **update)
    unresolved = FinancialPeriod(kind='quarter', fiscal_label="Q4'25", calendar='unresolved')
    unverified = changed(observation, period=unresolved, verification_status='unverified')
    assert unverified.period.end is None
    with pytest.raises(ValidationError):
        changed(unverified, verification_status='reviewed')
    with pytest.raises(ValidationError):
        FinancialPeriod(kind='ytd', fiscal_label='2025', end=date(2025, 12, 31))


def test_selector_distinguishes_inventory_binding_and_exact_periods():
    source, _, observation, task = sample()
    assert select_observations(task, [observation], []).status == 'source_absent'
    assert select_observations(task, [], [changed(source, status='unavailable')]).status == 'source_unavailable'
    assert select_observations(task, [], [source]).status == 'passage_not_found'
    unverified = changed(observation, verification_status='unverified')
    assert select_observations(task, [unverified], [source]).status == 'binding_unverified'
    differently_spelled = changed(task, period=changed(task.period, fiscal_label='Fiscal Year 2025'))
    assert select_observations(differently_spelled, [observation], [source]).status == 'supported'
    wrong_kind = changed(task, period=changed(task.period, kind='ytd'))
    assert select_observations(wrong_kind, [observation], [source]).status == 'passage_not_found'
    assert select_observations(changed(task, scope='segment'), [observation], [source]).status == 'passage_not_found'


def test_selector_requires_explicit_revision_and_respects_as_of():
    source, _, original, task = sample()
    newer_source = changed(source, source_id='amendment', version_id='amended-bytes',
                           source_hash='b' * 64, publication_date=date(2026, 3, 1))
    newer = changed(original, observation_id='revenue-revised', value='1250', source=newer_source)
    pins = [source, newer_source]
    assert select_observations(task, [original, newer], pins).status == 'conflicting'
    revised = changed(newer, supersedes_observation_ids=(original.observation_id,),
                       revision_evidence=(original.evidence[4],))
    assert select_observations(task, [original, revised], pins).observation_ids == (revised.observation_id,)
    assert select_observations(task, [original, revised], pins, revision_policy='as_reported').observation_ids == (original.observation_id,)
    assert select_observations(task, [original, revised], pins, as_of=date(2026, 2, 15)).observation_ids == (original.observation_id,)
    assert select_observations(task, [original], [source], as_of=date(2026, 1, 1)).status == 'passage_not_found'
    unknown = changed(source, publication_date=None)
    assert select_observations(task, [changed(original, source=unknown)], [unknown], as_of=date(2026, 4, 1)).status == 'ambiguous'
    assert select_observations(task, [revised], pins).status == 'conflicting'
    other = changed(original, period=changed(original.period, kind='ytd'))
    assert select_observations(task, [other, revised], pins).status == 'conflicting'
    cyclic_original = changed(original, supersedes_observation_ids=(revised.observation_id,),
                              revision_evidence=(original.evidence[4],))
    assert select_observations(task, [cyclic_original, revised], pins).status == 'conflicting'
    same_date_revised = changed(revised, source=changed(newer_source, publication_date=source.publication_date))
    assert select_observations(task, [cyclic_original, same_date_revised],
                               [source, same_date_revised.source]).reason == 'Revision lineage contains a cycle'


def test_selector_preserves_all_30_allowed_digits_during_scale_normalization():
    source, _, observation, task = sample(value='100000000000000000000000000001')
    different = changed(observation, observation_id='different', value='100000000000000000000000000002')
    assert select_observations(task, [observation, different], [source]).status == 'conflicting'
