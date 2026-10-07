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

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from app.extensions import db, limiter
from app.notifications import services

bp = Blueprint("notifications", __name__, url_prefix="/api/v1/notifications")

MAX_LIMIT = 50
DEFAULT_LIMIT = 20


def _error(code: int, message: str):
    """Return the project's JSON error shape with the given status."""
    return jsonify(error={"code": code, "message": message}), code


def _parse_iso8601(value: str) -> datetime | None:
    """Parse an ISO-8601 timestamp, returning None on failure."""
    try:
        # Accept a trailing 'Z' as UTC.
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
    """List the current user's notifications, newest first.

    Query parameters:
      limit       — 1..50, default 20
      before      — ISO-8601 timestamp cursor (created_at of the last item)
      before_id   — notification id cursor (id of the last item)
      unread_only — "true"/"1" to restrict to unread

    Cursor pagination uses (before, before_id) as a composite key. Both
    must be supplied together; supplying only one is treated as no cursor
    and returns the newest page.
    """
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
    """Mark a single notification as read.

    Returns 204 on success — even if the notification was already read,
    because the operation is idempotent.

    Returns 404 if the notification does not exist for this user.
    """
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
    """Mark every unread notification for the current user as read.

    Returns the number of rows updated.
    """
    count = services.mark_all_notifications_read(current_user.id)
    db.session.commit()
    return jsonify({"marked": count}), 200


# ── Page blueprint ────────────────────────────────────────
# Separate blueprint from the JSON API. The API lives under
# /api/v1/notifications; the page lives under /notifications.
page_bp = Blueprint("notifications_page", __name__, url_prefix="/notifications")


@page_bp.get("/")
@login_required
def page():
    """Server-rendered notifications page.

    The page shell is rendered server-side. The list itself is loaded
    client-side by /static/js/notifications.js via the JSON API.
    """
    return render_template("pages/notifications/index.html")