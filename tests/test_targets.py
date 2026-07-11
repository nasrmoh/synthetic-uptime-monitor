from tests.conftest import client
from app.services import record_check_result


BASE_TEST_PAYLOAD = {
    "url": "www.thisisntreal.com",
    "method": "GET",
    "interval_seconds": 10,
    "timeout_seconds": 20,
    "failure_threshold": 50,
    "expected_status": 201
}

def test_get_targets_as_list(db_session):
    response = client.get("/targets/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)



def test_post_targets_happy(db_session):
    test_payload = BASE_TEST_PAYLOAD.copy()
    response = client.post("/targets", json=test_payload)
    assert "id" in response.json()
    assert response.status_code == 201

def test_post_targets_bad_body(db_session):
    # based on how the target endpoint works any parameters
    # That aren't supposed to be there will be discarded
    # So the only way to trigger a failure is by having a paremeter
    # be the incorrect type.
    test_payload = BASE_TEST_PAYLOAD.copy()
    test_payload["timeout_seconds"] = "wrong_type"
    response = client.post("/targets", json=test_payload)
    assert response.status_code == 422

def test_get_target_id(db_session):
    test_payload = BASE_TEST_PAYLOAD.copy()
    response = client.post("/targets", json=test_payload)
    made_id = response.json()["id"]
    response = client.get(f"/targets/{made_id}")
    assert response.status_code == 200

def test_get_target_id_not_found(db_session):
    made_id = -1
    response = client.get(f"/targets/{made_id}")
    assert response.status_code == 404


def test_patch_targets_happy(db_session):
    test_payload = BASE_TEST_PAYLOAD.copy()
    response = client.post("/targets", json=test_payload)
    assert response.status_code == 201
    resp_id = response.json()["id"]
    original_url = response.json()["url"]
    original_method = response.json()["method"]
    new_test_payload= {
        "url" : "www.thisisnotatallreal"
    }
    response = client.patch(f"/targets/{resp_id}", json=new_test_payload)
    assert response.status_code == 200
    new_url = response.json()["url"]
    new_method = response.json()["method"]
    assert original_method == new_method
    assert original_url != new_url

def test_patch_targets_bad_body(db_session):
    test_payload = BASE_TEST_PAYLOAD.copy()
    response = client.post("/targets", json=test_payload)
    assert response.status_code == 201
    resp_id = response.json()["id"]
    new_test_payload= {
        "interval_seconds" : "WHAT IS THIS???"
    }
    response = client.patch(f"/targets/{resp_id}", json=new_test_payload)
    assert response.status_code == 422

def test_patch_targets_not_found_id(db_session):
    test_payload = BASE_TEST_PAYLOAD.copy()
    response = client.post("/targets", json=test_payload)
    new_test_payload= {
        "url" : "www.thisisnotatallreal"
    }
    response = client.patch(f"/targets/{-1}", json=new_test_payload)
    assert response.status_code == 404



def test_create_result(db_session):
    test_payload = BASE_TEST_PAYLOAD.copy()
    response = client.post("/targets", json=test_payload)
    target_id = response.json()["id"]
    status = 200
    error = None
    latency = 500
    # Since we don't want to cache the values in our test (might have a test to do this later too), we just record the
    # check result
    record_check_result(db_session, rd=None, status_code=status, error_class=error, target_id=target_id, latency_ms=latency, cache=False)
    response = client.get(f"/targets/{target_id}/results")
    assert response.status_code == 200 # check the route works
    assert response.json() # check the route returns a non-empty list
    # check the fields are the correct values
    # since all tests work on an empty test database inserting one guarantees that the value is in the first index
    # that is returned
    assert response.json()[0]["status_code"] == status
    assert response.json()[0]["error_class"] == error
    assert response.json()[0]["target_id"] == target_id
    assert response.json()[0]["latency_ms"] == latency
