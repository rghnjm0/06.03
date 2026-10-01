"""HTTP smoke tests for the public account and security middleware."""
import re
import pytest


@pytest.fixture()
def client():
    from app import app
    app.config.update(TESTING=True, SECRET_KEY="test-secret-key")
    with app.test_client() as test_client:
        yield test_client


def test_login_page_renders(client):
    response = client.get('/login')
    assert response.status_code == 200
    assert 'Войти' in response.get_data(as_text=True)


def test_register_page_renders(client):
    response = client.get('/register')
    assert response.status_code == 200


def test_post_without_csrf_is_rejected(client):
    response = client.post('/logout', data={})
    assert response.status_code == 400


def test_security_headers_are_set(client):
    response = client.get('/login')
    assert response.headers.get('X-Content-Type-Options') == 'nosniff'
    csp = response.headers.get('Content-Security-Policy', '')
    assert "'unsafe-inline'" not in csp
    assert 'nonce-' in csp
    assert "img-src 'self' data:" in csp


def test_login_page_inline_script_uses_csp_nonce(client):
    response = client.get('/login')
    html = response.get_data(as_text=True)
    nonce = re.search(r"script-src 'self' 'nonce-([^']+)'", response.headers['Content-Security-Policy']).group(1)
    assert f'<style nonce="{nonce}"' in html


def test_csp_does_not_allow_unneeded_google_fonts(client):
    response = client.get('/login')
    csp = response.headers.get('Content-Security-Policy', '')
    assert 'fonts.googleapis.com' not in csp
    assert 'fonts.gstatic.com' not in csp


def test_admin_clients_template_avoids_inline_user_data_handlers():
    from pathlib import Path
    template = Path(__file__).resolve().parents[1] / 'templates' / 'admin' / 'clients.html'
    html = template.read_text(encoding='utf-8')
    assert 'onsubmit=' not in html.lower()
    assert '{{ c.Фамилия }}' not in html.split('data-confirm=', 1)[-1]


def test_cdn_styles_and_scripts_have_sri():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / 'templates'
    for relative in ('base.html', 'admin/base_admin.html'):
        html = (root / relative).read_text(encoding='utf-8')
        for line in html.splitlines():
            if 'cdn.jsdelivr.net' in line or 'cdnjs.cloudflare.com' in line:
                if '<script' in line or '<link' in line:
                    assert 'integrity=' in line, f'SRI missing in {relative}: {line.strip()}'


def test_health_endpoint_is_minimal_and_healthy(client):
    response = client.get('/healthz')
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
