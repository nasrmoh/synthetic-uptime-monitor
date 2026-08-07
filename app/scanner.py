import structlog
from app.models import EndpointTarget
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.job import Job
from sqlalchemy import select
from app.db import get_db_with_context
from app.checker import perform_check
from app.metrics import targets_enabled

CHECK_TARGET_PREFIX = 'check-target-'


def target_scanner(scheduler: AsyncIOScheduler):
    # Reconciles APScheduler's live job list against Postgres's current
    # set of enabled targets. Runs periodically (see lifespan.py, added as
    # its own scheduled job) so that targets enabled/disabled/created
    # after startup get their check jobs added/removed without restarting
    # the app.
    with get_db_with_context() as db:
        statement = select(EndpointTarget).where(EndpointTarget.enabled)
        res = db.execute(statement).scalars().all()

    expected_ids = set()
    current_ids = set()
    res_value: EndpointTarget  # type hint only, for IDE/type-checker support in the loop below; no value assigned here
    id_to_check_time = (
        {}
    )  # dictionary to quickly get the interval seconds from the target id
    for res_value in res:
        id_to_check_time[res_value.id] = res_value.interval_seconds
        expected_ids.add(res_value.id)

    # Walk APScheduler's actual job list rather than trusting any cached
    # state, so this stays correct even if a previous target_scanner run
    # was skipped or the app restarted.
    current_jobs = []
    for job in scheduler.get_jobs():
        if job.id.startswith(CHECK_TARGET_PREFIX):
            current_jobs.append(job)
    c_job: Job  # type hint only, same purpose as res_value above
    for c_job in current_jobs:
        # Job ids are stored as "check-target-<id>"; strip the prefix to
        # recover the bare target id for set comparison against expected_ids.
        current_ids.add(grab_target_id_from_job_name(c_job.id))

    structlog.get_logger().info(
        'jobs', expected_ids=list(expected_ids), current_ids=list(current_ids)
    )
    targets_enabled.set(len(list(expected_ids)))

    # Set difference gives exactly what changed since the last scan:
    # targets newly enabled (need a job) and targets no longer enabled
    # or no longer existing (job should be removed).
    jobs_to_add = expected_ids - current_ids
    jobs_to_remove = current_ids - expected_ids

    for job_id in jobs_to_add:
        scheduler.add_job(
            perform_check,
            trigger='interval',
            seconds=id_to_check_time[job_id],
            id=f'check-target-{job_id}',
            args=[job_id],
            max_instances=1,
            misfire_grace_time=2,
        )

    for job_id in jobs_to_remove:
        # job_id here is a bare int (from current_ids, which was already
        # stripped of the prefix above); re-add the prefix since
        # remove_job() needs the full job id string APScheduler uses.
        scheduler.remove_job(job_id=CHECK_TARGET_PREFIX + str(job_id))


def grab_target_id_from_job_name(job_name: str):
    # Assumes a structure where job_name is check-target-<<id_number>>
    return int(job_name.removeprefix(CHECK_TARGET_PREFIX))
