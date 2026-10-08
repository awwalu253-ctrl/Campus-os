"""Tests for Web Push subscription endpoints.

These tests run against the testing config, where PUSH_ENABLED=False.
That means no real push is ever dispatched — the endpoints are
exercised in isolation.

Multi-user tests use a SINGLE test client with login/logout/login.
Flask's test client shares cookie state across multiple instances
created from the same app, so two clients would inherit each other's
session. Login and logout through the same client is the reliable way
to switch users mid-test.
"""
import uuid

import pytest

from app.auth import services as auth_services
from app.extensions import db
from app.notifications.models import PushSubscription


# ── Fixtures ──────────────────────────────────────────────
@pytest.fixture
def two_users(app):
    """Two users with known passwords, for HTTP login in tests."""
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        u1 = auth_services.create_user(
            email=f"push-a-{suffix}@example.com",
            password="testpass1234",
            display_name="Push A",
        )
        u2 = auth_services.create_user(
            email=f"push-b-{suffix}@example.com",
            password="testpass1234",
            display_name="Push B",
        )
        db.session.commit()
        return {
            "u1_id": u1.id,
            "u2_id": u2.id,
            "u1_email": u1.email,
            "u2_email": u2.email,
        }


# ── HTTP login helpers ────────────────────────────────────
def _http_login(client, email):
    r = client.post(
        "/auth/login",
        data={"email": email, "password": "testpass1234"},
    )
    assert r.status_code in (302, 303), f"login failed for {email}: {r.status_code}"


def _http_logout(client):
    r = client.post("/auth/logout")
    assert r.status_code in (302, 303)


def _payload(endpoint_suffix="test-1"):
    return {
        "endpoint": f"https://example.com/push/{endpoint_suffix}",
        "keys": {"p256dh": "A" * 87, "auth": "B" * 22},
    }


# ── VAPID public key ──────────────────────────────────────
def test_vapid_endpoint_returns_key(app, client, two_users):
    _http_login(client, two_users["u1_email"])
    r = client.get("/api/v1/notifications/vapid-public-key")
    assert r.status_code == 200
    body = r.get_json()
    assert "key" in body
    assert isinstance(body["key"], str)
    assert len(body["key"]) > 40


def test_vapid_endpoint_requires_auth(client):
    r = client.get("/api/v1/notifications/vapid-public-key")
    assert r.status_code == 401


# ── Subscribe ─────────────────────────────────────────────
def test_subscribe_creates_row(app, client, two_users):
    _http_login(client, two_users["u1_email"])
    r = client.post("/api/v1/notifications/subscribe", json=_payload("create"))
    assert r.status_code == 201
    assert r.get_json() == {"status": "subscribed"}

    with app.app_context():
        row = PushSubscription.query.filter_by(
            endpoint="https://example.com/push/create"
        ).first()
        assert row is not None
        assert row.user_id == two_users["u1_id"]


def test_subscribe_requires_auth(client):
    r = client.post("/api/v1/notifications/subscribe", json=_payload("anon"))
    assert r.status_code == 401


def test_subscribe_rejects_missing_fields(app, client, two_users):
    _http_login(client, two_users["u1_email"])
    r = client.post("/api/v1/notifications/subscribe", json={})
    assert r.status_code == 400
    assert "endpoint" in r.get_json()["error"]["message"].lower()


def test_subscribe_rejects_non_https_endpoint(app, client, two_users):
    _http_login(client, two_users["u1_email"])
    payload = _payload("insecure")
    payload["endpoint"] = "http://example.com/push/insecure"
    r = client.post("/api/v1/notifications/subscribe", json=payload)
    assert r.status_code == 400
    assert "https" in r.get_json()["error"]["message"].lower()


def test_subscribe_is_idempotent_on_endpoint(app, client, two_users):
    _http_login(client, two_users["u1_email"])
    payload = _payload("dupe")

    r1 = client.post("/api/v1/notifications/subscribe", json=payload)
    assert r1.status_code == 201

    r2 = client.post("/api/v1/notifications/subscribe", json=payload)
    assert r2.status_code == 200
    assert r2.get_json() == {"status": "updated"}

    with app.app_context():
        count = PushSubscription.query.filter_by(endpoint=payload["endpoint"]).count()
        assert count == 1


def test_subscribe_reassigns_endpoint_to_new_user(app, client, two_users):
    """If the same endpoint moves from user A to user B, the row is
    reassigned. The endpoint identifies the device, not the account."""
    with app.app_context():
        db.session.add(PushSubscription(
            user_id=two_users["u1_id"],
            endpoint="https://example.com/push/handed-over",
            p256dh="X" * 87,
            auth="Y" * 22,
        ))
        db.session.commit()

    _http_login(client, two_users["u2_email"])
    payload = _payload("handed-over")
    r = client.post("/api/v1/notifications/subscribe", json=payload)
    assert r.status_code == 200

    with app.app_context():
        row = PushSubscription.query.filter_by(endpoint=payload["endpoint"]).one()
        assert row.user_id == two_users["u2_id"]


# ── Unsubscribe ───────────────────────────────────────────
def test_unsubscribe_removes_own_subscription(app, client, two_users):
    _http_login(client, two_users["u1_email"])
    payload = _payload("unsub")
    client.post("/api/v1/notifications/subscribe", json=payload)

    r = client.post(
        "/api/v1/notifications/unsubscribe",
        json={"endpoint": payload["endpoint"]},
    )
    assert r.status_code == 200
    assert r.get_json()["deleted"] == 1

    with app.app_context():
        assert PushSubscription.query.filter_by(endpoint=payload["endpoint"]).count() == 0


def test_unsubscribe_cannot_delete_other_users_subscription(app, client, two_users):
    """Single client, login/logout/login. User A subscribes. User B
    then tries to unsubscribe A's endpoint. The row must survive."""
    payload = _payload("foreign")

    # User A logs in and subscribes
    _http_login(client, two_users["u1_email"])
    r = client.post("/api/v1/notifications/subscribe", json=payload)
    assert r.status_code == 201

    with app.app_context():
        row = PushSubscription.query.filter_by(endpoint=payload["endpoint"]).one()
        assert row.user_id == two_users["u1_id"]

    # User A logs out
    _http_logout(client)

    # User B logs in and tries to unsubscribe A's endpoint
    _http_login(client, two_users["u2_email"])
    r = client.post(
        "/api/v1/notifications/unsubscribe",
        json={"endpoint": payload["endpoint"]},
    )
    assert r.status_code == 200
    assert r.get_json()["deleted"] == 0

    # Row still exists, still owned by A
    with app.app_context():
        row = PushSubscription.query.filter_by(endpoint=payload["endpoint"]).one()
        assert row.user_id == two_users["u1_id"]


def test_unsubscribe_requires_auth(client):
    r = client.post(
        "/api/v1/notifications/unsubscribe",
        json={"endpoint": "https://x.com/y"},
    )
    assert r.status_code == 401