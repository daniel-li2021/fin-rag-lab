"""Explicit, confirmed business metadata; unknown values remain null."""
from datetime import date
from uuid import UUID
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceMetadata(BaseModel):
    model_config = ConfigDict(extra='forbid')
    company_id: str | None = Field(None, max_length=100)
    company_name: str | None = Field(None, max_length=200)
    fiscal_year: int | None = Field(None, ge=1900, le=2200)
    fiscal_quarter: int | None = Field(None, ge=1, le=4)
    period_kind: Literal['annual', 'quarterly', 'event', 'unknown'] = 'unknown'
    period_start: date | None = None
    period_end: date | None = None
    period_label: str | None = Field(None, max_length=200)
    publication_date: date | None = None
    document_type: Literal['10-K', '10-Q', 'earnings_release', 'earnings_presentation',
                           'transcript', 'note', 'article', 'other', 'unknown'] = 'unknown'
    review_status: Literal['unreviewed', 'confirmed', 'needs_review'] = 'unreviewed'

    @model_validator(mode='after')
    def valid_period(self):
        if self.period_start and self.period_end and self.period_start > self.period_end:
            raise ValueError('Period start must precede period end')
        return self


class SourceRegistration(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['pdf', 'text', 'markdown', 'url']
    title: str = Field(min_length=1, max_length=300)
    locator: str | None = Field(None, max_length=2048)
    metadata: SourceMetadata = Field(default_factory=SourceMetadata)
    request_key: str | None = Field(None, min_length=1, max_length=100)


class SourceFilters(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source_id: UUID | None = None
    version_id: UUID | None = None
    company_id: str | None = None
    fiscal_year: int | None = Field(None, ge=1900, le=2200)
    fiscal_quarter: int | None = Field(None, ge=1, le=4)
    document_type: str | None = None

    @model_validator(mode='after')
    def version_needs_source(self):
        if self.version_id and not self.source_id:
            raise ValueError('An explicit version requires its source_id')
        return self
