# app.py
"""Точка входа в приложение отеля «Уют».

Маршруты и служебная логика вынесены в отдельные модули,
чтобы проект было проще поддерживать и расширять.
"""
import os
import secrets
import hmac
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from flask import Flask, request, session, abort, g, jsonify
from db import DB_NAME, ensure_database_ready
from utils import init_uploads, sync_room_statuses, register_context_processors
from routes.public import register_public_routes
from routes.account import register_account_routes
from routes.admin import register_admin_routes
from hotel_logic import ensure_extended_schema
from routes.payments import payments_bp, ensure_payment_schema
from routes.features import features_bp, ensure_features_schema

app = Flask(__name__)

# Log to stdout (container-friendly) and optionally to a rotating file.
app.logger.setLevel(logging.INFO)
if not any(getattr(handler, "_uyut_handler", False) for handler in app.logger.handlers):
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    stream_handler._uyut_handler = True
    app.logger.addHandler(stream_handler)
    log_path = os.environ.get("UYUT_LOG_FILE")
    if log_path:
        log_file = Path(log_path).expanduser()
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        file_handler._uyut_handler = True
        app.logger.addHandler(file_handler)
if os.environ.get("UYUT_ENV", "development").lower() == "production" and not os.environ.get("UYUT_SECRET_KEY"):
    raise RuntimeError("UYUT_SECRET_KEY must be set in production")
app.secret_key = os.environ.get("UYUT_SECRET_KEY") or secrets.token_hex(32)
app.config["UPLOAD_FOLDER"] = "static/images/rooms"
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
is_production = os.environ.get("UYUT_ENV", "development").lower() == "production"
app.config["SESSION_COOKIE_SECURE"] = is_production or os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
app.config["PERMANENT_SESSION_LIFETIME"] = 60 * 60 * 8
app.config["SESSION_REFRESH_EACH_REQUEST"] = True

# Всегда используем БД проекта, а не случайную БД из текущей рабочей папки.
ensure_database_ready()


@app.context_processor
def inject_security_helpers():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    nonce = getattr(g, "csp_nonce", None)
    if not nonce:
        nonce = secrets.token_urlsafe(18)
        g.csp_nonce = nonce
    return {"csrf_token": token, "csp_nonce": nonce}


@app.before_request
def csrf_protect():
    if request.method != "POST":
        return
    expected = session.get("_csrf_token")
    supplied = request.form.get("_csrf_token") or request.headers.get("X-CSRF-Token")
    if not expected or not supplied or not hmac.compare_digest(str(expected), str(supplied)):
        abort(400, description="Недействительный CSRF-токен.")


# Rate-limit поиска в SQLite (общий для всех worker-процессов одного хоста).
_SEARCH_WINDOW_SEC = 60
_SEARCH_MAX_HITS = 30


def _ensure_rate_limit_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rate_limit_hits (
            key TEXT NOT NULL,
            ts REAL NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rate_limit_key_ts ON rate_limit_hits(key, ts)")


@app.before_request
def rate_limit_search():
    if request.endpoint not in ("search_rooms", "availability"):
        return
    import time
    now = time.time()
    ip = (request.headers.get("X-Forwarded-For") or request.remote_addr or "unknown").split(",")[0].strip()
    key = f"search:{ip}"
    try:
        from db import get_db
        conn = get_db()
        try:
            _ensure_rate_limit_table(conn)
            cutoff = now - _SEARCH_WINDOW_SEC
            conn.execute("DELETE FROM rate_limit_hits WHERE ts < ?", (cutoff,))
            count = conn.execute(
                "SELECT COUNT(*) FROM rate_limit_hits WHERE key=? AND ts >= ?",
                (key, cutoff),
            ).fetchone()[0]
            if count >= _SEARCH_MAX_HITS:
                conn.commit()
                abort(429, description="Слишком много запросов поиска. Подождите минуту.")
            conn.execute("INSERT INTO rate_limit_hits(key, ts) VALUES(?, ?)", (key, now))
            conn.commit()
        finally:
            conn.close()
    except Exception:
        # Не роняем публичные страницы из-за сбоя rate-limit
        current_app.logger.exception("rate_limit_search failed")


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    nonce = getattr(g, "csp_nonce", None)
    if nonce:
        # CSP без 'unsafe-inline'/'unsafe-eval': инлайн только с nonce.
        # CDN-скрипты/стили дополнительно защищены SRI (integrity) в шаблонах.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' data:; "
            "font-src 'self' data: https://cdnjs.cloudflare.com; "
            f"style-src 'self' 'nonce-{nonce}' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            f"script-src 'self' 'nonce-{nonce}' https://cdn.jsdelivr.net; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'self'; "
            "form-action 'self'; "
            "connect-src 'self'; "
            "upgrade-insecure-requests"
        )
    if request.is_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response

init_uploads()
register_context_processors(app)
register_public_routes(app)
register_account_routes(app)
register_admin_routes(app)
app.register_blueprint(payments_bp)
app.register_blueprint(features_bp)
ensure_extended_schema()
ensure_payment_schema()
ensure_features_schema()



@app.get("/healthz")
def health_check():
    """Lightweight liveness/readiness probe; does not expose database details."""
    from db import get_db
    conn = get_db()
    try:
        conn.execute("SELECT 1").fetchone()
    except Exception:
        app.logger.exception("Health check failed: database unavailable")
        return jsonify(status="unhealthy"), 503
    finally:
        conn.close()
    return jsonify(status="ok"), 200


if __name__ == "__main__":
    if not os.path.exists(DB_NAME):
        print("База данных не найдена. Запустите: python db.py")
    else:
        sync_room_statuses()
        app.run(debug=False, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "5000")))
