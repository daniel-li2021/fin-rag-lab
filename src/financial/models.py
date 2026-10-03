"""Immutable, reviewed financial sidecar contracts; no database or model calls."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class FinancialRecord(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, str_strip_whitespace=True)


class PinnedSource(FinancialRecord):
    source_id: str = Field(min_length=1)
    version_id: str = Field(min_length=1)
    build_id: str = Field(min_length=1)
    source_hash: str = Field(pattern=r'^[a-fA-F0-9]{64}$')
    company_id: str = Field(min_length=1)
    publication_date: date | None = None
    status: Literal['available', 'unavailable'] = 'available'

    @field_validator('publication_date')
    @classmethod
    def supported_publication_date(cls, value):
        if value and not 1900 <= value.year <= 2200:
            raise ValueError('Publication years must be between 1900 and 2200')
        return value


class FinancialPeriod(FinancialRecord):
    kind: Literal['quarter', 'ytd', 'annual', 'instant']
    start: date | None = None
    end: date | None = None
    fiscal_label: str = Field(min_length=1)
    calendar: str = Field(default='fiscal', min_length=1)

    @model_validator(mode='after')
    def valid_interval(self):
        if any(d and not 1900 <= d.year <= 2200 for d in (self.start, self.end)):
            raise ValueError('Financial period years must be between 1900 and 2200')
        if self.calendar == 'unresolved':
            if self.start is not None and self.end is not None and self.start > self.end:
                raise ValueError('Known period boundaries must be ordered')
            return self
        if self.end is None:
            raise ValueError('Resolved periods require an end date')
        if self.kind == 'instant':
            if self.start is not None:
                raise ValueError('An instant has no duration start')
        elif self.start is None or self.start > self.end:
            raise ValueError('A duration requires start <= end')
        return self

    def identity(self) -> tuple:
        """Dates/calendar own identity; fiscal label spelling does not."""
        return (self.kind, self.start, self.end, self.calendar,
                self.fiscal_label if self.calendar == 'unresolved' else None)


class EvidenceLink(FinancialRecord):
    model_config = ConfigDict(extra='forbid', frozen=True, str_strip_whitespace=False)
    role: Literal['value', 'row_label', 'column_period', 'unit', 'basis', 'scope']
    block_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=1)
    row_index: int | None = Field(default=None, ge=0)
    column_index: int | None = Field(default=None, ge=0)
    page_number: int | None = Field(default=None, ge=1)

    @field_validator('block_id', 'text')
    @classmethod
    def nonblank_original(cls, value):
        if not value.strip():
            raise ValueError('Evidence identity and text must be nonblank')
        return value

    @model_validator(mode='after')
    def valid_locator(self):
        span = self.char_start is not None and self.char_end is not None
        cell = self.row_index is not None and self.column_index is not None
        if (self.char_start is None) != (self.char_end is None):
            raise ValueError('Both character offsets are required')
        if (self.row_index is None) != (self.column_index is None):
            raise ValueError('Both cell coordinates are required')
        if span == cell:
            raise ValueError('Provide exactly one original span or table cell locator')
        if span and self.char_end <= self.char_start:
            raise ValueError('Character span must be nonempty')
        return self


class FinancialObservation(FinancialRecord):
    observation_id: str = Field(min_length=1)
    company_id: str = Field(min_length=1)
    metric_id: str = Field(min_length=1)
    original_label: str = Field(min_length=1)
    value: str = Field(min_length=1)
    unit: Literal['currency', 'percent', 'count', 'ratio']
    currency: str | None = Field(default=None, pattern=r'^[A-Z]{3}$')
    scale: str = '1'
    scope: str = Field(default='consolidated', min_length=1)
    basis: str = Field(default='GAAP', min_length=1)
    period: FinancialPeriod
    source: PinnedSource
    evidence: tuple[EvidenceLink, ...]
    verification_status: Literal['unverified', 'reviewed'] = 'unverified'
    review_revision: str | None = Field(default=None, min_length=1)
    supersedes_observation_ids: tuple[str, ...] = ()
    revision_evidence: tuple[EvidenceLink, ...] = ()
    reported: bool = True

    @field_validator('value', 'scale', mode='before')
    @classmethod
    def finite_decimal_string(cls, value):
        if not isinstance(value, str) or len(value) > 64:
            raise ValueError('Financial numbers must be decimal strings')
        try:
            number = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError('Invalid decimal string') from exc
        if not number.is_finite():
            raise ValueError('Financial numbers must be finite')
        if len(number.as_tuple().digits) > 30 or not -30 <= number.as_tuple().exponent <= 29 or number.adjusted() > 29:
            raise ValueError('Financial numbers exceed the 30-digit bound')
        return value

    @model_validator(mode='after')
    def valid_observation(self):
        if self.company_id != self.source.company_id:
            raise ValueError('Observation company must match pinned source')
        if not 0 < Decimal(self.scale) <= Decimal('1e12'):
            raise ValueError('Scale must be positive and at most 1e12')
        if (self.unit == 'currency') != (self.currency is not None):
            raise ValueError('Only currency amounts require a currency')
        if self.unit in ('percent', 'ratio') and Decimal(self.scale) != 1:
            raise ValueError('Percent and ratio observations use scale 1')
        if self.verification_status == 'reviewed':
            if self.period.calendar == 'unresolved':
                raise ValueError('Reviewed observations require confirmed period boundaries')
            roles = {link.role for link in self.evidence}
            if roles != {'value', 'row_label', 'column_period', 'unit', 'basis', 'scope'}:
                raise ValueError('Reviewed observations require all six evidence roles')
            if not self.review_revision:
                raise ValueError('Reviewed observations require a review revision')
        if self.observation_id in self.supersedes_observation_ids:
            raise ValueError('An observation cannot supersede itself')
        if len(set(self.supersedes_observation_ids)) != len(self.supersedes_observation_ids):
            raise ValueError('Duplicate revision predecessors')
        if self.supersedes_observation_ids and not self.revision_evidence:
            raise ValueError('Revision lineage requires original revision evidence')
        return self


class CoverageTask(FinancialRecord):
    task_id: str = Field(min_length=1)
    company_id: str = Field(min_length=1)
    metric_id: str = Field(min_length=1)
    period: FinancialPeriod
    scope: str = Field(default='consolidated', min_length=1)
    basis: str = Field(default='GAAP', min_length=1)


CoverageStatus = Literal['supported', 'ambiguous', 'source_absent', 'source_unavailable',
                         'passage_not_found', 'binding_unverified', 'non_comparable', 'conflicting']


class CoverageResult(FinancialRecord):
    task_id: str
    status: CoverageStatus
    observation_ids: tuple[str, ...] = ()
    reason: str = Field(min_length=1)
