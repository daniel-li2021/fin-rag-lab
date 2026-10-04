"""Bounded explicit financial research; reviewed originals own every number."""
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.storage.models import ResearchSelection
from .models import CoverageTask, CoverageResult, FinancialObservation
from .observations import validate_observation, select_observations
from .calculations import CalculationRequest, calculate


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    question: str = Field(min_length=1, max_length=4000)
    selections: tuple[ResearchSelection, ...] = Field(min_length=1, max_length=18)
    tasks: tuple[CoverageTask, ...] = Field(min_length=1, max_length=6)
    observations: tuple[FinancialObservation, ...] = Field(default=(), max_length=100)
    calculations: tuple[CalculationRequest, ...] = Field(default=(), max_length=6)
    mode: Literal['lookup', 'comparison', 'ranking'] = 'lookup'
    as_of: date | None = None
    revision_policy: Literal['latest_reviewed', 'as_reported'] = 'latest_reviewed'

    @model_validator(mode='after')
    def bounded_plan(self):
        ids = {t.task_id for t in self.tasks}
        if len(ids) != len(self.tasks):
            raise ValueError('Task IDs must be unique')
        if len({t.company_id for t in self.tasks}) > 3 or len({t.period.identity() for t in self.tasks}) > 3:
            raise ValueError('Narrow research to three companies and three periods')
        if len({o.observation_id for o in self.observations}) != len(self.observations):
            raise ValueError('Observation IDs must be unique')
        if any(c.start_task_id not in ids or c.end_task_id not in ids for c in self.calculations):
            raise ValueError('Calculation operands must reference required tasks')
        if self.mode == 'ranking' and self.calculations:
            raise ValueError('Rank observations or calculate explicitly in separate requests')
        return self


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def run_research(request: ResearchRequest, snapshot: dict) -> dict:
    """Execute against one preloaded authorized snapshot; no active pointers or model calls."""
    pins = snapshot['sources']
    accepted, rejected = [], []
    for observation in request.observations:
        try:
            accepted.append(validate_observation(observation, snapshot['blocks'].get(observation.source.build_id, []), pins))
        except ValueError as exc:
            rejected.append({'observation_id': observation.observation_id, 'reason': str(exc)})
    coverage = []
    for task in request.tasks:
        cell = select_observations(task, accepted, pins, request.as_of, request.revision_policy)
        if cell.status == 'source_absent' and any(
                item['metadata'].get('company_id') == task.company_id for item in snapshot['inventory']):
            cell = CoverageResult(task_id=task.task_id, status='source_unavailable',
                reason='Selected company has no available build with confirmed metadata')
        if cell.status == 'passage_not_found' and any(
                o.company_id == task.company_id and o.metric_id == task.metric_id
                and o.period.identity() == task.period.identity() and o.scope == task.scope and o.basis == task.basis
                for o in request.observations if o.observation_id in {r['observation_id'] for r in rejected}):
            cell = CoverageResult(task_id=task.task_id, status='binding_unverified',
                reason='Matching candidates failed reviewed original binding validation')
        coverage.append(cell)
    by_id = {o.observation_id: o for o in accepted}
    supported = {c.task_id: by_id[c.observation_ids[0]] for c in coverage if c.status == 'supported'}
    receipts, gaps = [], []
    for calculation in request.calculations:
        if calculation.start_task_id not in supported or calculation.end_task_id not in supported:
            gaps.append({'operation': calculation.operation, 'reason': 'A required operand is not supported'})
            continue
        try:
            receipts.append(calculate(calculation, supported[calculation.start_task_id], supported[calculation.end_task_id]))
        except ValueError as exc:
            gaps.append({'operation': calculation.operation, 'reason': str(exc)})
    if request.mode == 'comparison' and len(supported) > 1:
        facts = list(supported.values())
        dimensions = {(o.metric_id, o.scope, o.basis, o.unit, o.currency, o.period.kind, o.period.calendar) for o in facts}
        same_interval = len({o.period.identity() for o in facts}) == 1
        cross_company = len({o.company_id for o in facts}) > 1
        if len(dimensions) != 1 or (cross_company and not same_interval):
            gaps.append({'operation': 'comparison', 'reason': 'Facts have incompatible definitions, units, scopes or periods; shown separately'})
    ranked = []
    if request.mode == 'ranking':
        if len(supported) != len(request.tasks):
            gaps.append({'operation': 'ranking', 'reason': 'Every requested candidate must be supported'})
        else:
            dimensions = {(o.metric_id, o.basis, o.unit, o.currency, o.period.identity()) for o in supported.values()}
            # Cross-company rankings need one scope; within-company segment rankings may vary scope.
            if len(dimensions) != 1 or (len({o.company_id for o in supported.values()}) > 1
                    and len({o.scope for o in supported.values()}) != 1):
                gaps.append({'operation': 'ranking', 'reason': 'Ranking candidates are not comparable'})
            else:
                from decimal import Decimal, localcontext
                with localcontext() as context:
                    context.prec = 100
                    ranked = sorted(supported, key=lambda key: (-Decimal(supported[key].value) * Decimal(supported[key].scale), key))
    missing = [c for c in coverage if c.status != 'supported']
    outcome = ('clarify' if any(c.status == 'ambiguous' for c in coverage) else
               'refuse' if not supported else 'qualified_answer' if missing or gaps else 'answer')
    lines = []
    for task in request.tasks:
        observation = supported.get(task.task_id)
        if observation:
            unit = (observation.currency or observation.unit) + (' × ' + observation.scale if observation.scale != '1' else '')
            interval = (f' ({observation.period.start} to {observation.period.end}; {observation.period.calendar})'
                        if observation.period.start and observation.period.end else '')
            lines.append(f'{task.company_id} / {task.metric_id} / {task.period.fiscal_label}{interval} / {task.scope} / '
                         f'{task.basis}: {observation.value} {unit} [{observation.observation_id}]')
    lines.extend(f'{r.operation}: {r.displayed_result} [{r.observation_ids[0]}] [{r.observation_ids[1]}]' for r in receipts)
    lines.extend(limitation for receipt in receipts for limitation in receipt.limitations)
    if ranked:
        lines.append('Ranking (descending, ties share a value): ' + ', '.join(ranked))
    lines.extend(f'{c.task_id}: {c.status} — {c.reason}' for c in missing)
    lines.extend(f'{g["operation"]}: {g["reason"]}' for g in gaps)
    if not lines:
        lines = ['No requested fact has a reviewed original binding.']
    code_files = sorted(Path(__file__).parent.glob('*.py'))
    code_hash = hashlib.sha256(b''.join(p.name.encode() + p.read_bytes() for p in code_files)).hexdigest()
    result = {'contract_version': 'financial-research-v1', 'outcome': outcome, 'answer': '\n'.join(lines),
        'request': request.model_dump(mode='json'), 'manifest': [s.model_dump(mode='json') for s in pins],
        'inventory': snapshot['inventory'], 'coverage': [c.model_dump(mode='json') for c in coverage],
        'observations': [o.model_dump(mode='json') for o in accepted], 'rejected_observations': rejected,
        'calculations': [r.model_dump(mode='json') for r in receipts], 'calculation_gaps': gaps,
        'ranking': ranked, 'citations': {o.observation_id: {'source': o.source.model_dump(mode='json'),
            'evidence': [e.model_dump(mode='json') for e in o.evidence]} for o in supported.values()},
        'code_hash': code_hash, 'usage': {'planner_calls': 0, 'generator_calls': 0, 'embedding_calls': 0,
                                      'cost_usd': '0'}}
    result['run_id'] = hashlib.sha256(_canonical(result).encode()).hexdigest()
    return result
