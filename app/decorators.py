# coding=utf-8

from functools import wraps

from flask import abort
from flask_login import current_user

from .models import Permission


def permission_required(permission):
    def decorator(fun):
        @wraps(fun)
        def decorated_function(*args, **kwargs):
            if not current_user.can(permission):
                abort(403)
            return fun(*args, **kwargs)

        return decorated_function

    return decorator


def admin_required(fun):
    return permission_required(Permission.ADMINISTER)(fun)
