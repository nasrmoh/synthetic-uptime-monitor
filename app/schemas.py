"""
Pydantic schemas for request validation and response serialization.
"""
from pydantic import BaseModel, model_validator
from pydantic.v1 import ConfigDict
from datetime import datetime


class TargetCreate(BaseModel):
    url: str
    method: str
    timeout_seconds: int
    interval_seconds: int
    failure_threshold: int
    expected_status: int

    @model_validator(mode="after")
    def checktime_lt_timeout_interval(self):
        if self.interval_seconds < self.timeout_seconds:
            raise ValueError(f"timeout_seconds: {self.timeout_seconds} must be less than interval checks complete: {self.interval_seconds}")
        return self


class TargetResponse(BaseModel):
    # Without this, Pydantic expects a dict, not a SQLAlchemy object.
    # from_attributes=True lets it read fields by attribute access instead
    # (target.id, target.url, ...), so a route can return an EndpointTarget
    # directly and have it serialize correctly.
    model_config = ConfigDict(from_attributes=True)
    id: int
    url: str
    method: str
    timeout_seconds: int
    interval_seconds: int
    failure_threshold: int
    expected_status: int
    enabled: bool
    created_at: datetime
    updated_at: datetime | None = None


class TargetUpdate(BaseModel):
    url: str | None = None
    method: str | None = None
    timeout_seconds: int | None = None
    interval_seconds: int | None = None
    failure_threshold: int | None = None
    expected_status: int | None = None
    enabled: bool | None = None

    @model_validator(mode="after")
    def checktime_lt_timeout_interval(self):
        if (self.timeout_seconds is not None) and (self.interval_seconds is not None):
            if self.interval_seconds < self.timeout_seconds:
                    raise ValueError(
                        f"timeout_seconds: {self.timeout_seconds} must be less than interval checks complete: {self.interval_seconds}")
            return self


class CheckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status_code : int
    error_class: str | None = None
    target_id: int
    checked_at: datetime
    latency_ms: int