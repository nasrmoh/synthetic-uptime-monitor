"""
Pydantic schemas for request validation and response serialization.
"""
from pydantic import BaseModel
from pydantic.v1 import ConfigDict
from datetime import datetime


class TargetCreate(BaseModel):
    url: str
    method: str
    interval_seconds: int
    timeout_seconds: int
    failure_threshold: int
    expected_status: int

class TargetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    url: str
    method: str
    interval_seconds: int
    timeout_seconds: int
    failure_threshold: int
    expected_status: int
    enabled: bool
    created_at: datetime
    updated_at: datetime | None = None


class TargetUpdate(BaseModel):
    url: str | None = None
    method: str | None = None
    interval_seconds: int | None = None
    timeout_seconds: int | None = None
    failure_threshold: int | None = None
    expected_status: int | None = None
    enabled: bool | None = None