"""Notification HTTP API.

All endpoints are scoped to the authenticated user. Recipient isolation
is enforced in the service layer — this module never trusts a
recipient_id from the client.

Success responses use ``jsonify({...})`` with an explicit status code.
Error responses are produced by ``app.core.errors`` and use the shape
``{"error": {"code": N, "message": "..."}}``. The error handler detects
``/api/`` paths and returns JSON automatically.

CSRF protection is enabled app-wide. The POST endpoints require a valid
``csrf_token`` from the client.

This module also exposes a second blueprint for the server-rendered
notifications page at ``/notifications/``. The page blueprint is kept
separate from the JSON API blueprint because the two URL prefixes are
different (``/api/v1/notifications`` vs ``/notifications``) and Flask
blueprints cannot host routes with unrelated prefixes.
"""
from datetime import datetime

from flask import Blueprint, current_app, jsonify, render_template, request
from flask_login import current_user, login_required

from app.extensions import db, limiter
from app.notifications import services
from app.notifications.models import PushSubscription

bp = Blueprint("notifications", __name__, url_prefix="/api/v1/notifications")

MAX_LIMIT = 50
DEFAULT_LIMIT = 20


def _error(code: int, message: str):
    """Return the project's JSON error shape with the given status."""
    return jsonify(error={"code": code, "message": message}), code


def _parse_iso8601(value: str) -> datetime | None:
    """Parse an ISO-8601 timestamp, returning None on failure."""
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


# ── List ──────────────────────────────────────────────────
@bp.get("/")
@login_required
@limiter.limit("120 per minute")
def list_notifications():
    """List the current user's notifications, newest first."""
    raw_limit = request.args.get("limit", str(DEFAULT_LIMIT))
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        return _error(400, "limit must be an integer.")

    if limit < 1 or limit > MAX_LIMIT:
        return _error(400, f"limit must be between 1 and {MAX_LIMIT}.")

    raw_before = request.args.get("before")
    raw_before_id = request.args.get("before_id")

    before_dt = None
    if raw_before and raw_before_id:
        before_dt = _parse_iso8601(raw_before)
        if before_dt is None:
            return _error(400, "before must be an ISO-8601 timestamp.")

    unread_only = request.args.get("unread_only", "").lower() in {"1", "true", "yes"}

    rows = services.get_user_notifications(
        current_user.id,
        limit=limit,
        before_created_at=before_dt,
        before_id=raw_before_id if before_dt else None,
        unread_only=unread_only,
    )

    items = [services.serialize(n) for n in rows]

    next_cursor = None
    if items:
        last = rows[-1]
        next_cursor = {
            "before": last.created_at.isoformat(),
            "before_id": last.id,
        }

    return jsonify({
        "notifications": items,
        "next_cursor": next_cursor,
    }), 200


# ── Unread count ──────────────────────────────────────────
@bp.get("/unread-count")
@login_required
@limiter.limit("240 per minute")
def unread_count():
    """Return the current user's unread notification count."""
    count = services.get_unread_count(current_user.id)
    return jsonify({"count": count}), 200


# ── Mark one read ─────────────────────────────────────────
@bp.post("/<notification_id>/read")
@login_required
@limiter.limit("60 per minute")
def mark_read(notification_id: str):
    """Mark a single notification as read. Returns 204 on success."""
    ok = services.mark_notification_read(notification_id, current_user.id)
    if not ok:
        return _error(404, "Notification not found.")
    db.session.commit()
    return "", 204


# ── Mark all read ─────────────────────────────────────────
@bp.post("/read-all")
@login_required
@limiter.limit("10 per minute")
def mark_all_read():
    """Mark every unread notification for the current user as read."""
    count = services.mark_all_notifications_read(current_user.id)
    db.session.commit()
    return jsonify({"marked": count}), 200


# ── Web Push: VAPID public key ────────────────────────────
@bp.get("/vapid-public-key")
@login_required
@limiter.limit("60 per minute")
def vapid_public_key():
    """Return the VAPID public key the client needs to subscribe."""
    key = current_app.config.get("VAPID_PUBLIC_KEY", "")
    if not key:
        return _error(503, "Push notifications are not configured.")
    return jsonify({"key": key}), 200


# ── Web Push: subscribe ───────────────────────────────────
@bp.post("/subscribe")
@login_required
@limiter.limit("20 per minute")
def subscribe():
    """Register a Web Push subscription for the current user."""
    data = request.get_json(silent=True) or {}

    endpoint = (data.get("endpoint") or "").strip()
    keys = data.get("keys") or {}
    p256dh = (keys.get("p256dh") or "").strip()
    auth = (keys.get("auth") or "").strip()

    if not endpoint or not p256dh or not auth:
        return _error(400, "endpoint, keys.p256dh and keys.auth are required.")

    if not endpoint.startswith("https://"):
        return _error(400, "endpoint must be an https URL.")

    if len(endpoint) > 4096:
        return _error(400, "endpoint is too long.")

    if len(p256dh) > 255 or len(auth) > 64:
        return _error(400, "subscription keys are malformed.")

    user_agent = (request.headers.get("User-Agent") or "")[:255] or None

    existing = PushSubscription.query.filter_by(endpoint=endpoint).first()

    if existing is not None:
        existing.user_id = current_user.id
        existing.p256dh = p256dh
        existing.auth = auth
        existing.user_agent = user_agent
        db.session.commit()
        return jsonify({"status": "updated"}), 200

    sub = PushSubscription(
        user_id=current_user.id,
        endpoint=endpoint,
        p256dh=p256dh,
        auth=auth,
        user_agent=user_agent,
    )
    db.session.add(sub)
    db.session.commit()
    return jsonify({"status": "subscribed"}), 201


# ── Web Push: unsubscribe ─────────────────────────────────
@bp.post("/unsubscribe")
@login_required
@limiter.limit("20 per minute")
def unsubscribe():
    """Remove a Web Push subscription owned by the current user."""
    data = request.get_json(silent=True) or {}
    endpoint = (data.get("endpoint") or "").strip()

    if not endpoint:
        return _error(400, "endpoint is required.")

    deleted = (
        PushSubscription.query
        .filter_by(endpoint=endpoint, user_id=current_user.id)
        .delete(synchronize_session=False)
    )
    db.session.commit()
    return jsonify({"status": "unsubscribed", "deleted": deleted}), 200


# ── Web Push: status ──────────────────────────────────────
@bp.get("/push-status")
@login_required
@limiter.limit("60 per minute")
def push_status():
    """Return whether the current user has a push subscription.

    Optionally scope to a specific browser endpoint via ?endpoint=...
    so the client can verify that *this specific device* is registered
    for the *current* user.
    """
    endpoint = (request.args.get("endpoint") or "").strip() or None

    q = PushSubscription.query.filter_by(user_id=current_user.id)
    if endpoint:
        q = q.filter_by(endpoint=endpoint)

    return jsonify({"subscribed": q.count() > 0}), 200


# ── Page blueprint ────────────────────────────────────────
page_bp = Blueprint("notifications_page", __name__, url_prefix="/notifications")


@page_bp.get("/")
@login_required
def page():
    """Server-rendered notifications page."""
    return render_template("pages/notifications/index.html")