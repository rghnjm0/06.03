# app.py
"""Точка входа в приложение отеля «Уют».

Маршруты и служебная логика вынесены в отдельные модули,
чтобы проект было проще поддерживать и расширять.
"""
import os
import secrets
import hmac
from flask import Flask, request, session, abort
from db import DB_NAME, ensure_database_ready
from utils import init_uploads, sync_room_statuses, register_context_processors
from routes.public import register_public_routes
from routes.account import register_account_routes
from routes.admin import register_admin_routes
from hotel_logic import ensure_extended_schema
from routes.payments import payments_bp, ensure_payment_schema
from routes.features import features_bp, ensure_features_schema

app = Flask(__name__)
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
    return {"csrf_token": token}


@app.before_request
def csrf_protect():
    if request.method != "POST":
        return
    expected = session.get("_csrf_token")
    supplied = request.form.get("_csrf_token") or request.headers.get("X-CSRF-Token")
    if not expected or not supplied or not hmac.compare_digest(str(expected), str(supplied)):
        abort(400, description="Недействительный CSRF-токен.")


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data: https:; "
        "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "object-src 'none'; base-uri 'self'; frame-ancestors 'self'"
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



if __name__ == "__main__":
    if not os.path.exists(DB_NAME):
        print("База данных не найдена. Запустите: python db.py")
    else:
        sync_room_statuses()
        app.run(debug=False, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "5000")))
