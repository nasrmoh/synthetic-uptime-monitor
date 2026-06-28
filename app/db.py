from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from typing import Optional
from sqlalchemy.orm import relationship
from datetime import datetime
from sqlalchemy import ForeignKey
from sqlalchemy import create_engine
from sqlalchemy import func
import os

# Engine is created at import time, so if "DATABASE_URL" is not configured then the App will crash
engine = create_engine(os.environ["DATABASE_URL"])



class Base(DeclarativeBase):
    pass

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
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # we use server_default so that the server side controls the timestamp
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


