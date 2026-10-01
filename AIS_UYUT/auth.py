"""Авторизация и проверки доступа."""
from functools import wraps
from flask import session, flash, redirect, url_for
from werkzeug.security import check_password_hash, generate_password_hash


def password_matches(stored, supplied):
    """Проверяет как новые хэши, так и старые учебные пароли при миграции."""
    if not stored:
        return False
    if stored.startswith(("scrypt:", "pbkdf2:", "argon2:")):
        try:
            return check_password_hash(stored, supplied)
        except ValueError:
            return False
    # Legacy-значения мигрируются отдельной процедурой; не принимаем открытые
    # пароли при обычной авторизации.
    return False


PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 256


def validate_password(password):
    """Единая серверная политика паролей для всех сценариев."""
    if not isinstance(password, str):
        raise ValueError("Пароль должен быть строкой.")
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Пароль должен содержать минимум {PASSWORD_MIN_LENGTH} символов.")
    if len(password) > PASSWORD_MAX_LENGTH:
        raise ValueError(f"Пароль не должен содержать более {PASSWORD_MAX_LENGTH} символов.")
    return password


def hash_password(password):
    validate_password(password)
    return generate_password_hash(password, method="scrypt")


def login_required(f):
    """Доступ только авторизованному гостю. Администратор — отдельная зона."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "client_id" not in session or session.get("user_role") != "client":
            flash("Требуется авторизация гостя", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_role") != "admin":
            flash("Недостаточно прав", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function
