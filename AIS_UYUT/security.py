"""Авторизация и проверки доступа."""
from functools import wraps
from flask import session, flash, redirect, url_for


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
