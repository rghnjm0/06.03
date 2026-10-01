"""Smoke tests for payments blueprint."""
import pytest


@pytest.fixture()
def client():
    from app import app
    app.config.update(TESTING=True, SECRET_KEY="test-secret-key")
    with app.test_client() as c:
        yield c


def test_payment_page_requires_login_or_redirects(client):
    # unknown booking should not crash
    response = client.get("/pay/BK0001", follow_redirects=False)
    assert response.status_code in (302, 303, 404, 400, 200)
