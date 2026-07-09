from tests.conftest import client

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