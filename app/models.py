"""
SQLAlchemy ORM models for the synthetic uptime monitor.
"""

from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy import func
from typing import Optional
from sqlalchemy.orm import relationship
from datetime import datetime
from sqlalchemy import ForeignKey

class Base(DeclarativeBase):
    pass
# Refer to https://docs.sqlalchemy.org/en/20/orm/quickstart.html for more info.
# See SQL Notes for the reasoning behind field choices and field constraints
class EndpointTarget(Base):
    __tablename__ = "endpoint_target"
    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str]
    method: Mapped[str]
    timeout_seconds: Mapped[int]
    interval_seconds: Mapped[int]
    failure_threshold: Mapped[int]
    expected_status: Mapped[int]
    enabled: Mapped[bool] = mapped_column(default=True)
    # we use server_default so that the server side controls the timestamp
    # it is possible to instead use default=func.now() but this could lead to differences in time for machines
    # located in different timezones. i.e., use the server as the source of truth
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[Optional[datetime]]
    # relationship() is Python-level only, not stored in the database
    # target.results gives all CheckResult rows for this target without writing a query
    results: Mapped[list["CheckResult"]] = relationship(back_populates="target")



# See SQL Notes for the reasoning behind field choices and field constraints
class CheckResult(Base):
    __tablename__ = "check_result"
    id: Mapped[int] = mapped_column(primary_key=True)
    status_code: Mapped[int]
    error_class: Mapped[Optional[str]]
    target_id: Mapped[int] = mapped_column(ForeignKey("endpoint_target.id"))
    checked_at: Mapped[datetime] = mapped_column(server_default=func.now())
    latency_ms: Mapped[int]
    # result.target gives the parent EndpointTarget without writing a query
    target: Mapped["EndpointTarget"] = relationship(back_populates="results")