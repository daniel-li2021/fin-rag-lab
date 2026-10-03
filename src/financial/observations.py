"""Validate retained originals and select exact reviewed facts without I/O.

Locator checks prove provenance, not semantics. A named review revision explicitly
attests the row/column/scope associations; this module never promotes candidates.
"""
from __future__ import annotations

import re
from graphlib import CycleError, TopologicalSorter
from datetime import date
from decimal import Decimal, localcontext
from typing import Literal, Sequence

from src.core.models import DocumentBlock
from src.financial.models import (CoverageResult, CoverageTask, EvidenceLink,
                                  FinancialObservation, PinnedSource)


def parse_decimal(text: str) -> Decimal:
    """Parse one original numeric cell; blank/dash/narrative are missing, not zero."""
    if not isinstance(text, str) or len(text) > 100:
        raise ValueError('Expected a bounded original numeric string')
    token = text.strip().replace('\u2212', '-')
    negative = token.startswith('(') and token.endswith(')')
    if negative:
        token = token[1:-1].strip()
    token = re.sub(r'^(?:USD|EUR|GBP|JPY|[$€£¥])\s*', '', token)
    token = re.sub(r'\s*%$', '', token).strip()
    if not re.fullmatch(r'[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?', token):
        raise ValueError('Original value is not a single numeric cell')
    if negative and token.startswith(('-', '+')):
        raise ValueError('Parenthesized value cannot carry another sign')
    number = Decimal(token.replace(',', ''))
    if len(number.as_tuple().digits) > 30 or number.as_tuple().exponent < -30:
        raise ValueError('Original value exceeds the 30-digit bound')
    return number.copy_negate() if negative else number


def _validate_link(link: EvidenceLink, blocks: dict[str, DocumentBlock]) -> None:
    block = blocks.get(link.block_id)
    if block is None:
        raise ValueError('Evidence block is absent from retained originals')
    if link.page_number is not None and link.page_number != block.page_number:
        raise ValueError('Evidence page does not match retained block')
    if link.row_index is not None:
        rows = (block.structured_data or {}).get('rows', [])
        try:
            if block.block_type != 'table' or not isinstance(rows, list):
                raise ValueError('Cell evidence requires original table rows')
            cell = rows[link.row_index][link.column_index]
            original = str(cell if cell is not None else '')
        except (IndexError, TypeError, KeyError) as exc:
            raise ValueError('Evidence cell is absent from original rows') from exc
    else:
        original = block.get_original_text()[link.char_start:link.char_end]
    if original != link.text:
        raise ValueError('Evidence text does not match exact original locator')


def _validate_unit(observation: FinancialObservation) -> None:
    text = ' '.join(link.text for link in observation.evidence if link.role in ('unit', 'value')).lower()
    scales = {'thousand': Decimal(1000), 'million': Decimal(1000000), 'billion': Decimal(1000000000)}
    found = {scale for word, scale in scales.items() if word in text}
    expected = next(iter(found)) if len(found) == 1 else Decimal(1)
    if len(found) > 1 or Decimal(observation.scale) != expected:
        raise ValueError('Original unit evidence does not support the declared scale')
    has_percent = bool(re.search(r'%|\bpercent(?:age)?\b', text))
    if has_percent != (observation.unit == 'percent'):
        raise ValueError('Percent unit requires original percent evidence')
    if observation.unit != 'currency' and re.search(r'[$€£¥]|\b(?:usd|eur|gbp|jpy|dollars|euros|yen)\b', text):
        raise ValueError('Original currency evidence contradicts declared non-currency unit')
    if observation.unit == 'currency':
        tokens = {'USD': ('usd', '$', 'u.s. dollars', 'us dollars'),
                  'EUR': ('eur', '€', 'euros'), 'GBP': ('gbp', '£', 'pounds'),
                  'JPY': ('jpy', '¥', 'yen')}
        if not any(token in text for token in tokens.get(observation.currency, (observation.currency.lower(),))):
            raise ValueError('Original unit evidence does not support currency')


def validate_observation(
    observation: FinancialObservation,
    blocks: Sequence[DocumentBlock],
    pinned_sources: Sequence[PinnedSource],
) -> FinancialObservation:
    """Check a reviewed sidecar against blocks from its exact pinned build.

    Callers must load blocks by the supplied source/version/build/hash identity,
    never concatenate unrelated builds. Review status alone cannot bypass this.
    """
    if observation.source not in pinned_sources or observation.source.status != 'available':
        raise ValueError('Observation source is outside the available pinned manifest')
    if observation.verification_status != 'reviewed' or not observation.reported:
        raise ValueError('Only reviewed reported observations can bind original values')
    block_map = {block.block_id: block for block in blocks}
    if len(block_map) != len(blocks):
        raise ValueError('Duplicate original block identities')
    for link in (*observation.evidence, *observation.revision_evidence):
        _validate_link(link, block_map)
    values = [link for link in observation.evidence if link.role == 'value']
    if len(values) != 1 or parse_decimal(values[0].text) != Decimal(observation.value):
        raise ValueError('One original value must normalize to the observation value')
    labels = [link.text for link in observation.evidence if link.role == 'row_label']
    if observation.original_label not in labels:
        raise ValueError('Original row label must match a reviewed label locator')
    value = values[0]
    if value.row_index is not None:
        for link in observation.evidence:
            if link.block_id != value.block_id or link.row_index is None:
                continue
            if link.role == 'row_label' and link.row_index != value.row_index:
                raise ValueError('Table value and row label must share an original row')
            if link.role == 'column_period' and link.column_index != value.column_index:
                raise ValueError('Table value and period must share an original column')
    _validate_unit(observation)
    return observation


def _dimensions(observation: FinancialObservation) -> tuple:
    return (observation.company_id, observation.metric_id, observation.scope,
            observation.basis, observation.period.identity())


def select_observations(
    task: CoverageTask,
    observations: Sequence[FinancialObservation],
    pinned_sources: Sequence[PinnedSource],
    as_of: date | None = None,
    revision_policy: Literal['latest_reviewed', 'as_reported'] = 'latest_reviewed',
) -> CoverageResult:
    """Select exact dimensions; newer publications alone never resolve conflicts.

    Supply observations already checked by validate_observation. Unknown publication
    dates cannot establish an historical knowledge boundary.
    """
    if revision_policy not in ('latest_reviewed', 'as_reported'):
        raise ValueError('Unsupported revision policy')
    if len({o.observation_id for o in observations}) != len(observations):
        raise ValueError('Observation IDs must be unique')
    def result(status, reason, candidates=()):
        return CoverageResult(task_id=task.task_id, status=status, reason=reason,
                              observation_ids=tuple(sorted(o.observation_id for o in candidates)))
    sources = [s for s in pinned_sources if s.company_id == task.company_id]
    if not sources:
        return result('source_absent', 'Company is absent from the pinned source inventory')
    available = [s for s in sources if s.status == 'available']
    if not available:
        return result('source_unavailable', 'Company snapshots are unavailable in the pinned inventory')
    related = [o for o in observations if o.company_id == task.company_id and o.metric_id == task.metric_id
               and o.source in available]
    dimensions = (task.company_id, task.metric_id, task.scope, task.basis, task.period.identity())
    exact = [o for o in related if _dimensions(o) == dimensions]
    if as_of is not None:
        if any(o.source.publication_date is None for o in exact):
            return result('ambiguous', 'Unknown publication date prevents as-of selection', exact)
        exact = [o for o in exact if o.source.publication_date <= as_of]
    if not exact:
        return result('passage_not_found', 'No observation covers the exact requested period, metric, scope and basis')
    reviewed = [o for o in exact if o.verification_status == 'reviewed' and o.reported]
    if not reviewed:
        return result('binding_unverified', 'Matching observations lack reviewed original bindings', exact)
    by_id = {o.observation_id: o for o in observations}
    # A reviewed fact revision is explicit, dimension-preserving lineage, never byte recency.
    pending, lineage = list(reviewed), {}
    while pending:
        observation = pending.pop()
        if observation.observation_id in lineage:
            continue
        lineage[observation.observation_id] = observation.supersedes_observation_ids
        for predecessor_id in observation.supersedes_observation_ids:
            predecessor = by_id.get(predecessor_id)
            if (predecessor is None or _dimensions(predecessor) != dimensions
                    or predecessor.verification_status != 'reviewed'
                    or predecessor.source not in available):
                return result('conflicting', 'Revision lineage is missing or changes requested dimensions', reviewed)
            if (observation.source.publication_date and predecessor.source.publication_date
                    and observation.source.publication_date < predecessor.source.publication_date):
                return result('conflicting', 'Revision publication predates its predecessor', reviewed)
            pending.append(predecessor)
    try:
        tuple(TopologicalSorter(lineage).static_order())
    except CycleError:
        return result('conflicting', 'Revision lineage contains a cycle', reviewed)
    predecessors = {p for o in reviewed for p in o.supersedes_observation_ids}
    if revision_policy == 'latest_reviewed':
        selected = [o for o in reviewed if o.observation_id not in predecessors]
    else:
        selected = [o for o in reviewed if not o.supersedes_observation_ids]
    if not selected:
        return result('conflicting', 'Revision lineage has no selectable root or terminal fact', reviewed)
    units = {(o.unit, o.currency) for o in selected}
    if len(units) != 1:
        return result('non_comparable', 'Matching observations use incompatible units or currencies', selected)
    with localcontext() as context:
        context.prec = 100
        values = {Decimal(o.value) * Decimal(o.scale) for o in selected}
    if len(values) != 1:
        return result('conflicting', 'Different reviewed values lack a resolving fact revision', selected)
    return result('supported', 'Exact reviewed observations cover the requested dimensions', selected)
