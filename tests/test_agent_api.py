"""Test Bedrock Agent API."""

import pytest
from fastapi.testclient import TestApplications
from agent_api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    """Test health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert "status" in response.json()


def test_invoke_requires_message(client):
    """Test /invoke requires message field."""
    response = client.post("/invoke", json={})
    assert response.status_code == 422  # Validation error


def test_invoke_with_message(client):
    """Test /invoke with valid message (may return error if agent not configured)."""
    response = client.post("/invoke", json={"message": "Hello"})
    assert response.status_code in [200, 503]  # Success or degraded
    data = response.json()
    assert "session_id" in data
    assert "trace_id" in data
    assert "status" in data
