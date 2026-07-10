"""
FastAPI route handlers for /target endpoints
"""

from app.db import get_db
from app.models import EndpointTarget, CheckResult
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.schemas import TargetCreate, TargetUpdate, TargetResponse, CheckResponse

router = APIRouter()



@router.post("", response_model=TargetResponse, status_code=201)
def target_post(target_create: TargetCreate, db: Session = Depends(get_db), response = Response()):
    # FastAPI validates the request body against TargetCreate before this runs
    # If invalid, a 422 is returned automatically, no manual validation needed

    # ** unpacks the dictionary into keyword arguments
    # EndpointTarget(**{"url": "...", "interval_seconds": 30})
    # becomes EndpointTarget(url="...", interval_seconds=30)
    # works because model_dump() keys match EndpointTarget column names
    target = EndpointTarget(**target_create.model_dump())


    db.add(target)
    db.commit()

    # refresh pulls the server-assigned fields (id, created_at, enabled)
    # back from the database into the target instance
    db.refresh(target)
    # FastAPI serializes target through TargetResponse via response_model
    return target



# Since we want to return a list of Target Responses, our response model bundles them as a list
@router.get("", response_model=list[TargetResponse])
def targets_all_get(db: Session = Depends(get_db)):
    statement = select(EndpointTarget) # We create the query on our SQLAlchemy model
    result = db.execute(statement).scalars().all()
    # This first executes the statement on our session
    # Then it unwraps the rows from their tuple container
    # .all() converts the result into a python list
    return result


@router.get("/{target_id}",response_model=TargetResponse)
def target_id_get(target_id : int, db:Session = Depends(get_db)):
    statement = select(EndpointTarget).where(EndpointTarget.id == target_id)
    # using .first() will return None in the case the value isn't there
    result = db.execute(statement).scalars().first()
    # .scalars().first() returns a single EndpointTarget instance or None if no row matches
    if not result:
        raise HTTPException(status_code=404, detail="Target Not Found")
    return result


@router.patch("/{target_id}", response_model=TargetResponse)
def target_id_patch(target_update : TargetUpdate, target_id : int, db: Session = Depends(get_db)):

    # first check that the id exists
    statement = select(EndpointTarget).where(EndpointTarget.id == target_id)
    result = db.execute(statement).scalars().first()
    if not result:
        raise HTTPException(status_code=404, detail="Target Not Found")

    # target_update comes from the client (TargetUpdate Pydantic schema)
    # result comes from the database (EndpointTarget SQLAlchemy instance)
    # model_fields_set contains only the fields the client actually sent
    # -- fields the client omitted are not in this set, so we never touch them
    for key in target_update.model_fields_set:
        # setattr(result, key, value) is equivalent to result.key = value
        # but works dynamically when the attribute name is a string
        # getattr(target_update, key) reads the new value off the Pydantic object
        setattr(result, key, getattr(target_update, key))

    # SQLAlchemy tracks attribute changes on ORM objects automatically
    # commit() generates an UPDATE statement for only the columns that changed
    db.commit()

    # refresh() updates result in place with the latest state from the database
    # no reassignment needed -- result already holds the fresh values after this
    db.refresh(result)
    return result


@router.get("/{target_id}/results", response_model=list[CheckResponse])
def result_id_get(target_id: int, db: Session = Depends(get_db)):
    # We hardcode the limit to 100, maybe changing this later?
    statement = select(CheckResult).where(CheckResult.target_id == target_id).order_by(CheckResult.checked_at.desc()).limit(100)
    result = db.execute(statement).scalars().all()
    return result