from functools import wraps
from flask import abort
from flask_login import current_user


def requiere_rol(*roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated or current_user.rol not in roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator
