"""Allowlisted Decimal operations over reviewed, bound observations only."""
from decimal import Decimal, localcontext, ROUND_HALF_UP
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .models import FinancialObservation


class CalculationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    operation: Literal['difference', 'growth', 'percentage_point_change', 'margin', 'delivery_to_production']
    start_task_id: str = Field(min_length=1)
    end_task_id: str = Field(min_length=1)
    decimal_places: int = Field(default=2, ge=0, le=6, strict=True)
    period_policy: Literal['exact_duration', 'reporting_kind'] = 'exact_duration'
    cross_company: bool = False


class CalculationReceipt(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    operation: str
    policy_version: str = 'decimal-v1-precision100-half-up'
    observation_ids: tuple[str, str]
    normalized_operands: tuple[str, str]
    formula: str
    result: str
    displayed_result: str
    unit: str
    period_policy: str
    limitations: tuple[str, ...] = ()
    citations: tuple[dict, dict]


def calculate(request: CalculationRequest, start: FinancialObservation,
              end: FinancialObservation) -> CalculationReceipt:
    """Call after original binding validation; failed compatibility never emits a result."""
    if any(o.verification_status != 'reviewed' or not o.review_revision for o in (start, end)):
        raise ValueError('Calculations require reviewed observations')
    if any(o.period.calendar == 'unresolved' or o.period.end is None or (
            o.period.kind != 'instant' and o.period.start is None) for o in (start, end)):
        raise ValueError('Calculations require resolved reporting dates')
    if start.scope != end.scope or start.basis != end.basis:
        raise ValueError('Operand scope and basis differ')
    if start.company_id != end.company_id and not request.cross_company:
        raise ValueError('Cross-company calculation must be explicit')
    same_period = (start.period.kind, start.period.start, start.period.end, start.period.calendar) == (
        end.period.kind, end.period.start, end.period.end, end.period.calendar)
    if start.period.kind != end.period.kind or start.period.calendar != end.period.calendar:
        raise ValueError('Operand reporting periods differ')
    same_metric = start.metric_id == end.metric_id
    op = request.operation
    if op == 'growth' and (start.company_id != end.company_id or same_period):
        raise ValueError('Growth requires one company across distinct reporting periods')
    if op in ('margin', 'delivery_to_production'):
        expected = ({'gross_profit', 'operating_income', 'net_income', 'net_income_parent'}, 'revenue') if op == 'margin' else (
            {'vehicle_deliveries'}, 'vehicle_production')
        if start.metric_id not in expected[0] or end.metric_id != expected[1] or not same_period:
            raise ValueError('Ratio requires the allowlisted numerator and same-period denominator')
        if start.company_id != end.company_id:
            raise ValueError('Ratios require one company')
    elif not same_metric:
        if op != 'difference' or not same_period or start.company_id != end.company_id or {
                start.metric_id, end.metric_id} != {'vehicle_production', 'vehicle_deliveries'}:
            raise ValueError('Incompatible metrics')
    if start.unit != end.unit or start.currency != end.currency:
        raise ValueError('Operand units or currencies differ')
    limitations = ()
    if not same_period:
        if start.company_id != end.company_id:
            raise ValueError('Cross-company differences require the same interval')
        if end.period.end <= start.period.end:
            raise ValueError('Trend periods must be chronological')
        if start.period.kind != 'instant':
            days = [(o.period.end - o.period.start).days for o in (start, end)]
            if days[0] != days[1]:
                if request.period_policy != 'reporting_kind':
                    raise ValueError('Unequal reporting durations require an explicit policy')
                limitations = ('Reporting durations differ; compared under explicit reporting-kind policy.',)
    if op == 'percentage_point_change' and start.unit != 'percent':
        raise ValueError('Percentage-point change requires percent observations')
    if op == 'difference' and start.unit == 'percent':
        raise ValueError('Percent operands require the percentage_point_change operation')
    if op == 'margin' and start.unit != 'currency':
        raise ValueError('Margin requires profit and revenue in one currency')
    if op == 'delivery_to_production' and start.unit != 'count':
        raise ValueError('Operating ratio requires count observations')
    with localcontext() as ctx:
        ctx.prec = 100
        a, b = (Decimal(o.value) * Decimal(o.scale) for o in (start, end))
        if not all(v.is_finite() for v in (a, b)):
            raise ValueError('Nonfinite operand')
        if op == 'growth':
            if a <= 0:
                raise ValueError('Growth requires a positive baseline; request an absolute difference')
            value, formula, unit = (b - a) / a * 100, '(end - start) / start * 100', 'percent'
        elif op in ('margin', 'delivery_to_production'):
            if b <= 0:
                raise ValueError('Ratio denominator must be positive')
            value, formula, unit = a / b * 100, 'start / end * 100', 'percent'
        else:
            value, formula = b - a, 'end - start'
            unit = 'percentage points' if op == 'percentage_point_change' else start.currency or start.unit
        shown = value.quantize(Decimal(1).scaleb(-request.decimal_places), rounding=ROUND_HALF_UP)
    suffix = '%' if unit == 'percent' else ' ' + unit
    sign = '+' if op in ('difference', 'growth', 'percentage_point_change') else ''
    return CalculationReceipt(operation=op, observation_ids=(start.observation_id, end.observation_id),
        normalized_operands=(format(a, 'f'), format(b, 'f')), formula=formula, result=format(value, 'f'),
        displayed_result=format(shown, sign + 'f') + suffix, unit=unit, period_policy=request.period_policy,
        limitations=limitations, citations=tuple({'source': o.source.model_dump(mode='json'),
            'evidence': [e.model_dump(mode='json') for e in o.evidence]} for o in (start, end)))
