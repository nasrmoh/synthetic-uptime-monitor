from tests.conftest import client


def test_get_targets_as_list():
    response = client.get("/targets/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
