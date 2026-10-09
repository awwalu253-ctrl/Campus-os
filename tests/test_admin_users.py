"""Tests for the admin Users management page and actions."""
import uuid

import pytest

from app.auth import services as auth_services
from app.core.security import hash_password
from app.extensions import db
from app.models import User
from app.models.audit import AuditLog


@pytest.fixture
def admin(app):
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        u = User(
            email=f"admin-{suffix}@example.com",
            display_name="Admin",
            password_hash=hash_password("testpass1234"),
            role="platform_admin",
            status="active",
        )
        db.session.add(u)
        db.session.commit()
        return u.id


@pytest.fixture
def target_user(app):
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        u = auth_services.create_user(
            email=f"target-{suffix}@example.com",
            password="testpass1234",
            display_name="Target User",
        )
        db.session.commit()
        return u.id


def _login(client, user_id):
    with client.session_transaction() as s:
        s["_user_id"] = user_id
        s["_fresh"] = True


def test_users_list_requires_auth(client):
    r = client.get("/admin/users")
    assert r.status_code == 302


def test_users_list_requires_admin(app, client):
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        u = auth_services.create_user(
            email=f"student-{suffix}@example.com",
            password="testpass1234",
            display_name="Student",
        )
        db.session.commit()
        sid = u.id
    _login(client, sid)
    r = client.get("/admin/users")
    assert r.status_code == 403


def test_users_list_renders_for_admin(app, client, admin):
    _login(client, admin)
    r = client.get("/admin/users")
    assert r.status_code == 200
    assert b"Users" in r.data


def test_users_list_search_filters(app, client, admin, target_user):
    _login(client, admin)
    r = client.get("/admin/users?q=target")
    assert r.status_code == 200
    assert b"Target User" in r.data


def test_user_detail_renders(app, client, admin, target_user):
    _login(client, admin)
    r = client.get(f"/admin/users/{target_user}")
    assert r.status_code == 200
    assert b"Target User" in r.data


def test_suspend_requires_manage_users_perm(app, client, target_user):
    """Moderator can view, not suspend."""
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        m = User(
            email=f"mod-{suffix}@example.com",
            display_name="Mod",
            password_hash=hash_password("testpass1234"),
            role="moderator",
            status="active",
        )
        db.session.add(m)
        db.session.commit()
        mid = m.id
    _login(client, mid)
    r = client.post(f"/admin/users/{target_user}/suspend")
    assert r.status_code == 403


def test_suspend_writes_audit_and_updates_status(app, client, admin, target_user):
    _login(client, admin)
    r = client.post(f"/admin/users/{target_user}/suspend")
    assert r.status_code in (302, 303)

    with app.app_context():
        u = db.session.get(User, target_user)
        assert u.status == "suspended"

        log = (
            AuditLog.query
            .filter_by(action="user.suspend", entity_id=target_user)
            .order_by(AuditLog.created_at.desc())
            .first()
        )
        assert log is not None
        assert log.actor_id == admin
        assert log.before == {"status": "active"}
        assert log.after == {"status": "suspended"}


def test_restore_writes_audit_and_updates_status(app, client, admin, target_user):
    _login(client, admin)

    # First suspend so we have something to restore
    client.post(f"/admin/users/{target_user}/suspend")

    r = client.post(f"/admin/users/{target_user}/restore")
    assert r.status_code in (302, 303)

    with app.app_context():
        u = db.session.get(User, target_user)
        assert u.status == "active"

        log = (
            AuditLog.query
            .filter_by(action="user.restore", entity_id=target_user)
            .order_by(AuditLog.created_at.desc())
            .first()
        )
        assert log is not None
        assert log.after == {"status": "active"}


def test_admin_cannot_suspend_self(app, client, admin):
    _login(client, admin)
    r = client.post(f"/admin/users/{admin}/suspend", follow_redirects=False)
    assert r.status_code in (302, 303)

    with app.app_context():
        u = db.session.get(User, admin)
        assert u.status == "active"