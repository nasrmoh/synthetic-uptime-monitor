from app.models import EndpointTarget
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.job import Job
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db import  get_db_with_context
from app.checker import perform_check

CHECK_TARGET_PREFIX = "check-target-"


def target_scanner(scheduler : AsyncIOScheduler):
    with get_db_with_context() as db:
        statement = select(EndpointTarget).where(EndpointTarget.enabled)
        res = db.execute(statement).scalars().all()

    expected_ids = set()
    current_ids = set()
    res_value : EndpointTarget
    id_to_check_time = {} # dictionary to quickly get the interval seconds from the target id
    for res_value in res:
        id_to_check_time[res_value.id] = res_value.interval_seconds
        expected_ids.add(res_value.id)

    current_jobs = []
    for job in scheduler.get_jobs():
        if job.id.startswith(CHECK_TARGET_PREFIX):
            current_jobs.append(job)
    c_job : Job
    for c_job in current_jobs:
        current_ids.add(grab_target_id_from_job_name(c_job.id))

    print(f"expected_ids={expected_ids} current_ids={current_ids}")
    jobs_to_add = expected_ids - current_ids
    jobs_to_remove = current_ids - expected_ids

    for job_id in jobs_to_add:
        scheduler.add_job(perform_check, trigger="interval", seconds = id_to_check_time[job_id], id = f"check-target-{job_id}", args = [job_id], max_instances=1)

    for job_id in jobs_to_remove:
        scheduler.remove_job(job_id=CHECK_TARGET_PREFIX+str(job_id))




def grab_target_id_from_job_name(job_name : str):
    # Assumes a structure where job_name is check-target-<<id_number>>
    return int(job_name.removeprefix(CHECK_TARGET_PREFIX))







