from contextlib import contextmanager
from unittest.mock import patch
from unittest.mock import Mock

import pytest
from _pytest import unittest
from app.models import CheckResult, EndpointTarget
from app.checker import complete_check, perform_check, TargetNotFoundError
from app.services import record_check_result
import httpx
from sqlalchemy import select, text

setup_query = "INSERT INTO endpoint_target(url, method, timeout_seconds, interval_seconds, failure_threshold, expected_status, enabled) VALUES ('www.google.com', 'GET', 20, 10, 100, 200,  true)"




# @patch replaces httpx.get with a fake, but only as seen from inside
# app/checker.py (that's why the path is "app.checker.httpx.get", not
# "httpx.get"). It hands us that fake as the mock_get argument, and restores
# the real httpx.get automatically once the test finishes.
@patch("app.checker.httpx.get")
def test_checker_succeeds(mock_get):
    # A fake response object with just the attribute complete_check reads.
    fake_response = Mock(status_code=200)

    # Tells mock_get what to return when called.
    mock_get.return_value = fake_response
    # We call the function that we are actually testing
    val = complete_check("www.example.com", 5, 50)
    # now inside of this function its own call to `httpx.get` will be replaced with the mock

    assert val["status_code"] == 200
    assert val["target_id"] == 5
    assert val["error_class"] is None
    assert val["latency_ms"] >= 0


@patch("app.checker.httpx.get")
def test_checker_fails(mock_get):
    # side_effect makes the mock raise instead of return. We pass an
    # already-constructed instance (not the bare class) since RequestError
    # requires a message argument, and the mock would otherwise try to
    # construct one itself with none.
    mock_get.side_effect = httpx.RequestError("placeholder message")
    # placeholder message is there because otherwise we can't create the exception

    val = complete_check("www.example.com", 5, 50)

    assert val["status_code"] is None
    assert val["target_id"] == 5
    assert val["error_class"] == "RequestError"
    assert val["latency_ms"] >= 0




## ===== perform_check tests =====

def test_perform_check_raises_when_target_missing():
    pytest.raises(TargetNotFoundError, perform_check, -1)

# Note that perform check calls these two helper functions which we will also mock
@patch("app.checker.complete_check")
@patch("app.checker.record_check_result")
def test_perform_check_skips_when_target_disabled(mock_complete_check : Mock,mock_record_check_result : Mock, db_session): # Notice the order, are mocks are in order of patches.
    # Just setup code like the other tests
    db_session.execute(text(
        "INSERT INTO endpoint_target(url, method, timeout_seconds, interval_seconds, failure_threshold, expected_status, enabled) VALUES ('www.google.com', 'GET', 20, 10, 100, 200,  false)"))
    statement = select(EndpointTarget)
    res = db_session.execute(statement).scalars().first()
    target_id = res.id

    # This test requires overriding the call to get_db_with_context within perform_check
    # We create a mock version of that function, and since it is called within a with block we use context manager
    # to set that up. Then all we need to do is yield db_session as expected.

    @contextmanager
    def mock_get_db_with_context():
        yield db_session

    # Now using patch, we use the import relative to the function that is using it. perform check is located within
    # app.checker. And to it we pass our mock / overrided version of the function
    with patch("app.checker.get_db_with_context", mock_get_db_with_context):
        perform_check(target_id)
        mock_complete_check.assert_not_called()
        mock_record_check_result.assert_not_called()



# Note that perform check calls these two helper functions which we will also mock
@patch("app.checker.complete_check")
@patch("app.checker.record_check_result")
def test_perform_check_skips_when_target_enabled(mock_record_check_result : Mock, mock_complete_check : Mock, db_session): # Notice the order, are mocks are in reverse order of patches
    # Just setup code like the other tests
    db_session.execute(text(
        "INSERT INTO endpoint_target(url, method, timeout_seconds, interval_seconds, failure_threshold, expected_status, enabled) VALUES ('www.google.com', 'GET', 20, 10, 100, 200,  true)"))
    statement = select(EndpointTarget)
    res = db_session.execute(statement).scalars().first()
    target_id = res.id

    mock_return_values = {
        "target_id": target_id,
        "status_code": 404,
        "latency_ms": 2000,
        "error_class": None,
    }

    mock_complete_check.return_value = mock_return_values

    # This test requires overriding the call to get_db_with_context within perform_check
    # We create a mock version of that function, and since it is called within a with block we use context manager
    # to set that up. Then all we need to do is yield db_session as expected.

    @contextmanager
    def mock_get_db_with_context():
        yield db_session

    # Now using patch, we use the import relative to the function that is using it. perform check is located within
    # app.checker. And to it we pass our mock / overrided version of the function
    with patch("app.checker.get_db_with_context", mock_get_db_with_context):
        perform_check(target_id)
    # check that the correct values were inserted into our complete check mock
    mock_complete_check.assert_called_with("www.google.com", target_id, 20)

    # we're lazy and don't really want to mock the redis connection, so instead we just get what call values
    # were inserted into the mock record_check_result function
    # then we just assert the values match what complete_check returned.
    args, kwargs = mock_record_check_result.call_args
    assert kwargs["status_code"] == mock_complete_check.return_value["status_code"]
    assert kwargs["latency_ms"] == mock_complete_check.return_value["latency_ms"]
    assert kwargs["error_class"] == mock_complete_check.return_value["error_class"]




## ===== record_check_result tests =====

def test_record_checker_persists(db_session):
    db_session.execute(text("INSERT INTO endpoint_target(url, method, timeout_seconds, interval_seconds, failure_threshold, expected_status, enabled) VALUES ('www.google.com', 'GET', 20, 10, 100, 200,  true)"))
    statement = select(EndpointTarget)
    res_0 = db_session.execute(statement).scalars().first()
    id = res_0.id

    # Also handles the case where rd=None
    record_check_result(db= db_session, rd=None, status_code=404,error_class=None, target_id=id, latency_ms=100, cache=False)
    statement = select(CheckResult).where(CheckResult.target_id==id)
    res = db_session.execute(statement).scalars().first()

    assert res.status_code == 404
    assert res.error_class is None
    assert res.target_id == id
    assert res.latency_ms == 100


def test_record_check_result_skips_when_cache_true(db_session):
    rd = Mock()
    db_session.execute(text(setup_query))
    statement = select(EndpointTarget)
    res_0 = db_session.execute(statement).scalars().first()
    id = res_0.id

    record_check_result(db=db_session, rd=rd, status_code=404, error_class=None, target_id=id, latency_ms=100,
                        cache=True)
    rd.set.assert_called()


def test_record_check_result_skips_when_cache_false(db_session):
    rd = Mock()
    db_session.execute(text(setup_query))
    statement = select(EndpointTarget)
    res_0 = db_session.execute(statement).scalars().first()
    id = res_0.id

    record_check_result(db=db_session, rd=rd, status_code=404, error_class=None, target_id=id, latency_ms=100,
                        cache=False)
    rd.set.assert_not_called()


def test_record_check_result_not_valid_to_cache(db_session):
    assert pytest.raises(ValueError, record_check_result, db=db_session, rd=None, status_code=404, error_class=None, target_id=0, latency_ms=100,cache=True)