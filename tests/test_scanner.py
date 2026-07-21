from contextlib import contextmanager

from app.models import EndpointTarget
from sqlalchemy import text, select
from unittest.mock import patch, Mock
from app.scanner import target_scanner
from app.scanner import grab_target_id_from_job_name

query_1 = "INSERT INTO endpoint_target(url, method, timeout_seconds, interval_seconds, failure_threshold, expected_status, enabled) VALUES ('www.google.com', 'GET', 20, 10, 100, 200,  true)"
query_2 = "INSERT INTO endpoint_target(url, method, timeout_seconds, interval_seconds, failure_threshold, expected_status, enabled) VALUES ('www.example.com', 'GET', 20, 10, 100, 200,  true)"
query_3 = "INSERT INTO endpoint_target(url, method, timeout_seconds, interval_seconds, failure_threshold, expected_status, enabled) VALUES ('www.whereisthis.co.uk', 'GET', 20, 10, 100, 200,  true)"
query_4 = "INSERT INTO endpoint_target(url, method, timeout_seconds, interval_seconds, failure_threshold, expected_status, enabled) VALUES ('www.whereisthis.co.uk', 'GET', 20, 10, 100, 200,  false)"


CHECK_TARGET_PREFIX = "check-target-"

def test_target_scanner_adds_jobs_when_exepcted_gt_current(db_session):
    scheduler = Mock()
    # first we'll add about 3 enabled targets
    db_session.execute(text(query_1))
    db_session.execute(text(query_2))
    db_session.execute(text(query_3))
    statement = select(EndpointTarget)
    res = db_session.execute(statement).scalars().all()
    # debug. remove later
    print(res)
    id_0 = res[0].id
    id_1 = res[1].id
    id_2 = res[2].id

    # we pass to our target scanner the currently configured db_session
    @contextmanager
    def mock_get_db_with_context():
        yield db_session

    job_0 = Mock()
    job_1 = Mock()
    job_2 = Mock()
    job_0.id = CHECK_TARGET_PREFIX+f"{id_0}"
    job_1.id = CHECK_TARGET_PREFIX+f"{id_1}"
    job_2.id = CHECK_TARGET_PREFIX+f"{id_2}"


    with patch("app.scanner.get_db_with_context", mock_get_db_with_context):
        # This says that the current jobs in the scheduler are jobs 0 and 1. i.e.,
        # add job will add job 2
        with patch.object(scheduler, "get_jobs", return_value=[job_0, job_1]):
            target_scanner(scheduler)
            args, kwargs = scheduler.add_job.call_args
            # args is stored as a list :)
            assert kwargs["args"][0] == id_2


def test_target_scanner_removes_job_when_current_gt_expected(db_session):
    scheduler = Mock()
    # first we'll add about 3 enabled targets
    db_session.execute(text(query_1))
    db_session.execute(text(query_2))
    db_session.execute(text(query_4)) # similar to query 3 but with the endpoint toggled off
    statement = select(EndpointTarget)
    res = db_session.execute(statement).scalars().all()
    # debug. remove later
    print(res)
    id_0 = res[0].id
    id_1 = res[1].id
    id_2 = res[2].id

    # we pass to our target scanner the currently configured db_session
    @contextmanager
    def mock_get_db_with_context():
        yield db_session

    job_0 = Mock()
    job_1 = Mock()
    job_2 = Mock()
    job_0.id = CHECK_TARGET_PREFIX+f"{id_0}"
    job_1.id = CHECK_TARGET_PREFIX+f"{id_1}"
    job_2.id = CHECK_TARGET_PREFIX+f"{id_2}"



    with patch("app.scanner.get_db_with_context", mock_get_db_with_context):
        # This says that the current jobs in the scheduler are jobs 0, 1 and 2
        # We are to remove job 2
        with patch.object(scheduler, "get_jobs", return_value=[job_0, job_1, job_2]):
            target_scanner(scheduler)
            args, kwargs = scheduler.remove_job.call_args
            assert kwargs["job_id"] == job_2.id


def test_target_scanner_noop_when_expected_equals_current(db_session):
    scheduler = Mock()
    # first we'll add about 3 enabled targets
    db_session.execute(text(query_1))
    db_session.execute(text(query_2))
    db_session.execute(text(query_3))
    statement = select(EndpointTarget)
    res = db_session.execute(statement).scalars().all()
    # debug. remove later
    print(res)
    id_0 = res[0].id
    id_1 = res[1].id
    id_2 = res[2].id

    # we pass to our target scanner the currently configured db_session
    @contextmanager
    def mock_get_db_with_context():
        yield db_session

    job_0 = Mock()
    job_1 = Mock()
    job_2 = Mock()
    job_0.id = CHECK_TARGET_PREFIX+f"{id_0}"
    job_1.id = CHECK_TARGET_PREFIX+f"{id_1}"
    job_2.id = CHECK_TARGET_PREFIX+f"{id_2}"


    with patch("app.scanner.get_db_with_context", mock_get_db_with_context):
        # all jobs are in the expected and current sets. Nothing should be called
        with patch.object(scheduler, "get_jobs", return_value=[job_0, job_1, job_2]):
            target_scanner(scheduler)
            scheduler.add_job.assert_not_called()
            scheduler.remove_job.assert_not_called()


def test_target_scanner_ignores_non_check_target_jobs(db_session):
    scheduler = Mock()
    # first we'll add about 3 enabled targets
    db_session.execute(text(query_1))
    db_session.execute(text(query_2))
    db_session.execute(text(query_3))
    statement = select(EndpointTarget)
    res = db_session.execute(statement).scalars().all()
    # debug. remove later
    print(res)
    id_0 = res[0].id
    id_1 = res[1].id
    id_2 = res[2].id

    # we pass to our target scanner the currently configured db_session
    @contextmanager
    def mock_get_db_with_context():
        yield db_session

    job_0 = Mock()
    job_1 = Mock()
    job_2 = Mock()
    job_3 = Mock()
    job_0.id = CHECK_TARGET_PREFIX+f"{id_0}"
    job_1.id = CHECK_TARGET_PREFIX+f"{id_1}"
    job_2.id = CHECK_TARGET_PREFIX+f"{id_2}"
    job_3.id = "target_scanner"


    with patch("app.scanner.get_db_with_context", mock_get_db_with_context):
        # all jobs are in the expected and current sets. Nothing should be called
        # This test should also not have the scanner job being called.
        with patch.object(scheduler, "get_jobs", return_value=[job_0, job_1, job_2, job_3]):
            target_scanner(scheduler)
            scheduler.add_job.assert_not_called()
            scheduler.remove_job.assert_not_called()

