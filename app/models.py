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
    __tablename__ = 'endpoint_target'
    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str]
    method: Mapped[str]
    timeout_seconds: Mapped[int]
    interval_seconds: Mapped[int]
    failure_threshold: Mapped[int]
    expected_status: Mapped[int]
    enabled: Mapped[bool] = mapped_column(default=True)

    # server_default lets Postgres itself stamp the timestamp, rather than
    # the app doing it with default=func.now(). This makes Postgres the
    # single source of truth for "now," instead of depending on the clock
    # of whichever app instance happens to insert the row.
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # onupdate (not server_onupdate) is deliberate: onupdate=func.now()
    # makes SQLAlchemy inject the expression into the UPDATE statement it
    # generates. server_onupdate is hint-only and has no DDL effect, so it
    # would silently do nothing here.
    updated_at: Mapped[Optional[datetime]] = mapped_column(onupdate=func.now())

    # Tracks consecutive failures for this target. A gauge-style column
    # rather than counting rows in check_result on every read, since that
    # would mean scanning check_result for every /ready-style query as the
    # table grows. Incremented/reset by the checker flow, not here.
    current_failed_checks: Mapped[int] = mapped_column(server_default='0')

    # relationship() is Python-level only, not stored in the database.
    # target.results gives all CheckResult rows for this target without
    # writing a query manually.
    results: Mapped[list['CheckResult']] = relationship(
        back_populates='target'
    )


# See SQL Notes for the reasoning behind field choices and field constraints
class CheckResult(Base):
    __tablename__ = 'check_result'
    id: Mapped[int] = mapped_column(primary_key=True)

    # Optional because a request-level error (timeout, DNS failure, etc.)
    # means no HTTP response was ever received, so there's no status code
    # to record. See error_class below.
    status_code: Mapped[Optional[int]]

    # Only set for request-level errors (httpx exceptions where no response
    # was received), holding type(e).__name__. Left None for a completed
    # request that simply returned an unexpected status code, that's a
    # failure, not an error, and status_code above already captures it.
    error_class: Mapped[Optional[str]]

    target_id: Mapped[int] = mapped_column(ForeignKey('endpoint_target.id'))
    checked_at: Mapped[datetime] = mapped_column(server_default=func.now())
    latency_ms: Mapped[int]

    # result.target gives the parent EndpointTarget without writing a query.
    target: Mapped['EndpointTarget'] = relationship(back_populates='results')
