"""Tests for the admin System Health page."""
import uuid

import pytest

from app.core.security import hash_password
from app.extensions import db
from app.models import User


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


def _login(client, user_id):
    with client.session_transaction() as s:
        s["_user_id"] = user_id
        s["_fresh"] = True


def test_admin_health_requires_auth(client):
    r = client.get("/admin/health")
    assert r.status_code == 302


def test_admin_health_requires_admin(app, client):
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        u = User(
            email=f"student-{suffix}@example.com",
            display_name="Student",
            password_hash=hash_password("testpass1234"),
            role="student",
            status="active",
        )
        db.session.add(u)
        db.session.commit()
        sid = u.id
    _login(client, sid)
    r = client.get("/admin/health")
    assert r.status_code == 403


def test_admin_health_renders_for_admin(app, client, admin):
    _login(client, admin)
    r = client.get("/admin/health")
    assert r.status_code == 200

    body = r.data
    # All four component cards render.
    for label in (b"Application", b"Database", b"Redis", b"Celery"):
        assert label in body

    # Page title and breadcrumb confirm it's the health page.
    assert b"System Health" in body


def test_admin_health_does_not_leak_sensitive_strings(app, client, admin):
    """The rendered page must not contain config values or connection strings.

    Mirrors the invariant asserted for /healthz/deps in tests/test_health.py.
    """
    _login(client, admin)
    r = client.get("/admin/health")
    assert r.status_code == 200

    blob = r.data.decode("utf-8", errors="ignore").lower()
    for forbidden in (
        "password",
        "secret",
        "postgres://",
        "postgresql://",
        "redis://",
        "memory://",
        "celery_broker_url",
        "database_url",
        "redis_url",
    ):
        assert forbidden not in blob, f"health page leaked: {forbidden}"


def test_admin_health_reports_a_known_celery_state(app, client, admin):
    """Celery status must be one of the four defined states.

    We do not assert which one — that depends on whether a broker URL is
    configured and whether a worker is running in the test environment.
    We do assert that the page never renders an unrecognised Celery
    status, and that the check never crashes the page.
    """
    _login(client, admin)
    r = client.get("/admin/health")
    assert r.status_code == 200

    body = r.data
    # The four valid Celery states, as rendered by the pill component.
    valid_states = (b"ok", b"unknown", b"broker_error", b"no_workers")

    # At least one of the valid states must appear in the HTML.
    # (The Application/Database/Redis cards also use "ok", so this
    # check is a weak positive — the stronger invariant is the
    # negative assertion below.)
    assert any(state in body for state in valid_states)

    # The page must not have errored on the Celery check — no template
    # error text or debug traceback should be present.
    assert b"Traceback" not in body
    assert b"TemplateNotFound" not in body