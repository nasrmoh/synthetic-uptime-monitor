from unittest.mock import patch
from unittest.mock import Mock
import app.checker
import httpx


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
    val = app.checker.complete_check("www.example.com", 5, 50)
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

    val = app.checker.complete_check("www.example.com", 5, 50)

    assert val["status_code"] is None
    assert val["target_id"] == 5
    assert val["error_class"] == "RequestError"
    assert val["latency_ms"] >= 0

