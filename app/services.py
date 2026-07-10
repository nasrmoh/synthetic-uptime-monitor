from app.models import CheckResult
from sqlalchemy.orm import Session


def record_check_result(db : Session, status_code, error_class, target_id, latency_ms):
    check_result = CheckResult(status_code=status_code, error_class=error_class, target_id = target_id, latency_ms = latency_ms)
    # register object with SQLAlchemy
    db.add(check_result)
    # Since we don't need the id for anything, we can skip flush and go straight to commit
    db.commit()
    return check_result