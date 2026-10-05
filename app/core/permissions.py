from functools import wraps
from flask import abort
from flask_login import current_user


class Perm:
    ADMIN_VIEW = "admin.view"
    ADMIN_MANAGE_USERS = "admin.manage_users"
    ADMIN_MANAGE_UNIS = "admin.manage_universities"


_ROLE_PERMS: dict[str, set[str]] = {
    "student": set(),
    "moderator": {Perm.ADMIN_VIEW},
    "campus_admin": {Perm.ADMIN_VIEW, Perm.ADMIN_MANAGE_USERS},
    "platform_admin": {
        Perm.ADMIN_VIEW, Perm.ADMIN_MANAGE_USERS, Perm.ADMIN_MANAGE_UNIS,
    },
}


def has(perm: str) -> bool:
    if not current_user.is_authenticated:
        return False
    return perm in _ROLE_PERMS.get(current_user.role, set())


def requires(perm: str):
    def deco(fn):
        @wraps(fn)
        def inner(*a, **kw):
            if not has(perm):
                abort(403)
            return fn(*a, **kw)
        return inner
    return deco