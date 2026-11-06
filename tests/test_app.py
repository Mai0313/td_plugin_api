from fastapi.testclient import TestClient

from td_plugin_api.app import app


def test_healthz_reports_ok() -> None:
    response = TestClient(app).get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
