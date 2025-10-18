from fastapi.testclient import TestClient

from prooforigin.api.main import create_app


def test_app_factory_healthcheck():
    app = create_app()
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_rate_limiter_is_configured():
    app = create_app()
    assert hasattr(app.state, "limiter")
