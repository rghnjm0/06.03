from functools import wraps
from flask import abort, request
from flask_login import current_user
from . import db
from .models import AuditLog

def roles_required(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return deco

def audit(action, entity="", entity_id=None):
    if current_user.is_authenticated:
        db.session.add(AuditLog(
            user_id=current_user.id, action=action,
            entity=entity, entity_id=entity_id
        ))
        db.session.commit()
