"""Tests for the admin Notifications & Push overview page.

Covers the read-only dashboard at /admin/notifications. The page is
strictly read-only: no compose form, no send button, no moderation
actions. These tests assert:
  1. Auth is required.
  2. Permissions are enforced.
  3. The page renders for a platform admin.
  4. Sensitive push-subscription fields (endpoint, p256dh, auth) are
     never surfaced in the HTML, even when a subscription exists.
"""
import uuid

import pytest

from app.core.security import hash_password
from app.extensions import db
from app.models import User
from app.notifications.models import PushSubscription


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
def subscribed_user(app):
    """Create a user with a push subscription containing distinctive
    sentinel strings in the sensitive fields, so a leak is detectable.
    """
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        u = User(
            email=f"push-{suffix}@example.com",
            display_name="Push User",
            password_hash=hash_password("testpass1234"),
            role="student",
            status="active",
        )
        db.session.add(u)
        db.session.flush()

        sub = PushSubscription(
            user_id=u.id,
            endpoint="https://example.com/SENTINEL_ENDPOINT",
            p256dh="SENTINEL_P256DH",
            auth="SENTINEL_AUTH",
            user_agent="Mozilla/5.0 Test UA",
        )
        db.session.add(sub)
        db.session.commit()

        return {"user_id": u.id, "sub_id": sub.id}


def _login(client, user_id):
    with client.session_transaction() as s:
        s["_user_id"] = user_id
        s["_fresh"] = True


def test_admin_notifications_requires_auth(client):
    r = client.get("/admin/notifications")
    assert r.status_code == 302


def test_admin_notifications_requires_admin(app, client):
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
    r = client.get("/admin/notifications")
    assert r.status_code == 403


def test_admin_notifications_renders_for_admin(app, client, admin):
    _login(client, admin)
    r = client.get("/admin/notifications")
    assert r.status_code == 200

    body = r.data
    # Section labels present in the template.
    for label in (
        b"Notifications",
        b"Push subscriptions",
        b"By type",
        b"Recent notifications",
        b"Recent push subscriptions",
    ):
        assert label in body, f"missing section label: {label}"


def test_admin_notifications_does_not_leak_sensitive_strings(
    app, client, admin, subscribed_user
):
    """The page must never render a push subscription's endpoint,
    p256dh, or auth. We insert a row with sentinel values in those
    columns and assert none of the sentinels appear in the HTML.
    """
    _login(client, admin)
    r = client.get("/admin/notifications")
    assert r.status_code == 200

    blob = r.data.decode("utf-8", errors="ignore")
    for sentinel in (
        "SENTINEL_ENDPOINT",
        "SENTINEL_P256DH",
        "SENTINEL_AUTH",
    ):
        assert sentinel not in blob, f"admin page leaked: {sentinel}"

    # Column names must not appear either — same protection as the
    # /healthz/deps test: config keys and column names are leaks too.
    lowered = blob.lower()
    for forbidden in ("p256dh", "dedupe_key", "dedupe-key"):
        assert forbidden not in lowered, f"admin page mentions: {forbidden}"