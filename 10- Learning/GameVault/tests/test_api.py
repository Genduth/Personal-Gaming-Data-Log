import os

import pytest
from fastapi.testclient import TestClient

from gamevault.main import app

pytestmark = pytest.mark.skipif(
    "DATABASE_URL" not in os.environ,
    reason="DATABASE_URL is required for API integration tests",
)


def test_health_and_collector_authentication() -> None:
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"
        assert client.get("/v1/collector/catalog").status_code == 401
        response = client.get(
            "/v1/collector/catalog",
            headers={"Authorization": f"Bearer {os.environ['COLLECTOR_TOKEN']}"},
        )
        assert response.status_code == 200
        assert "aliases" in response.json()
