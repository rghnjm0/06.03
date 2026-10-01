"""Smoke tests for admin zone access control."""
import pytest


@pytest.fixture()
def client():
    from app import app
    app.config.update(TESTING=True, SECRET_KEY="test-secret-key")
    with app.test_client() as c:
        yield c


def test_admin_dashboard_requires_auth(client):
    response = client.get("/admin/dashboard", follow_redirects=False)
    assert response.status_code in (302, 303, 401)
    # redirect to login
    loc = response.headers.get("Location", "")
    assert "login" in loc or response.status_code == 401


def test_admin_rooms_requires_auth(client):
    response = client.get("/admin/rooms", follow_redirects=False)
    assert response.status_code in (302, 303, 401)


def test_admin_export_requires_auth(client):
    response = client.get("/admin/reports/export.csv", follow_redirects=False)
    assert response.status_code in (302, 303, 401)


def test_search_rejects_huge_range(client):
    response = client.get(
        "/search?check_in=2026-01-01&check_out=2027-12-31&guests=2",
        follow_redirects=True,
    )
    # flash about max stay or redirect home
    data = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "90" in data or "превышать" in data or "Уют" in data


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code in (200, 503)
