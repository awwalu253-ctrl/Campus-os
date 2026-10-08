"""Web Push sender.

Design rules enforced by this module:

1. Never raises to the caller. Push delivery failure must never
   propagate into a request transaction or a Celery task.
2. Never logs subscription endpoints, payloads, or VAPID keys.
3. Deletes subscriptions on 404/410 (permanent invalid).
4. Leaves subscriptions in place on transient failures (500, timeout,
   network error) so they can be retried on the next dispatch.
5. Enforces a per-call timeout and a per-request attempt cap.
6. Uses the current_app config for VAPID and policy.
7. Establishes its own Flask app context when needed, so it is safe to
   call from a request, a Celery task, or an after_commit listener that
   may fire after the request context has been torn down.
8. Uses a fresh, independent SQLAlchemy session for its own database
   access, so it can run inside after_commit without touching the
   caller's committed (unusable) session.
"""
import json
import logging
from datetime import datetime, timezone

from flask import current_app, has_app_context
from pywebpush import WebPushException, webpush
from sqlalchemy.orm import sessionmaker

from app.extensions import db
from app.notifications.models import PushSubscription

logger = logging.getLogger(__name__)


class PushResult:
    """Result of one push dispatch run."""

    __slots__ = ("sent", "deleted", "failed", "skipped")

    def __init__(self):
        self.sent = 0
        self.deleted = 0
        self.failed = 0
        self.skipped = 0

    def as_dict(self) -> dict:
        return {
            "sent": self.sent,
            "deleted": self.deleted,
            "failed": self.failed,
            "skipped": self.skipped,
        }


def _fresh_session():
    """Return a new Session bound to the app's engine.

    The caller is responsible for closing it.
    """
    Session = sessionmaker(bind=db.engine, expire_on_commit=False)
    return Session()


def _build_payload(notification) -> dict:
    """Construct the payload sent to the browser."""
    return {
        "title": notification.title or "Campus OS",
        "body": notification.body or "",
        "url": notification.action_url or "/",
        "tag": notification.id,
    }


def _vapid_claims() -> dict:
    """Build the VAPID claims dict from config."""
    subject = current_app.config.get("VAPID_SUBJECT") or "mailto:admin@campusos.app"
    return {"sub": subject}


def _delete_subscription_by_id(sub_id: str, reason: str) -> None:
    """Delete a subscription by id using a fresh session.

    Safe to call from after_commit — never touches the caller's session.
    Never raises.
    """
    logger.info("push: deleting stale subscription id=%s reason=%s", sub_id, reason)
    try:
        sess = _fresh_session()
        try:
            sess.query(PushSubscription).filter_by(id=sub_id).delete()
            sess.commit()
        finally:
            sess.close()
    except Exception:
        logger.exception("push: failed to delete stale subscription id=%s", sub_id)


def _touch_last_success(sub_id: str) -> None:
    """Update last_success_at on a fresh session. Best-effort, never raises."""
    try:
        sess = _fresh_session()
        try:
            sess.query(PushSubscription).filter_by(id=sub_id).update(
                {"last_success_at": datetime.now(timezone.utc)}
            )
            sess.commit()
        finally:
            sess.close()
    except Exception:
        pass


def _send_snapshot(snap: dict, payload: dict, timeout: int) -> str:
    """Send a push from a plain dict snapshot of a subscription.

    Returns "sent" | "deleted" | "failed". Never raises.
    """
    try:
        webpush(
            subscription_info={
                "endpoint": snap["endpoint"],
                "keys": {
                    "p256dh": snap["p256dh"],
                    "auth": snap["auth"],
                },
            },
            data=json.dumps(payload),
            vapid_private_key=current_app.config["VAPID_PRIVATE_KEY"],
            vapid_claims=_vapid_claims(),
            timeout=timeout,
        )
        _touch_last_success(snap["id"])
        return "sent"

    except WebPushException as exc:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)

        if status in (404, 410):
            _delete_subscription_by_id(snap["id"], f"http_{status}")
            return "deleted"

        logger.warning(
            "push: transient failure id=%s status=%s error=%s",
            snap["id"], status, type(exc).__name__,
        )
        return "failed"

    except Exception as exc:
        logger.warning(
            "push: unexpected failure id=%s error=%s",
            snap["id"], type(exc).__name__,
        )
        return "failed"


def dispatch_for_notification(notification) -> PushResult:
    """Send a push for one notification to all its subscriptions.

    Safe to call from a request, from a Celery task, or from an
    SQLAlchemy after_commit listener that may fire after the request
    context has been torn down.

    This function NEVER raises.
    """
    result = PushResult()

    if has_app_context():
        return _dispatch_inner(notification, result)

    try:
        from app import create_app
        app = create_app()
    except Exception:
        logger.exception("push: could not create app for dispatch")
        return result

    try:
        with app.app_context():
            return _dispatch_inner(notification, result)
    except Exception:
        logger.exception("push: unexpected error during dispatch")
        return result


def _dispatch_inner(notification, result: PushResult) -> PushResult:
    """The actual dispatch work. Runs inside a Flask app context."""
    if not current_app.config.get("PUSH_ENABLED", True):
        return result

    if not current_app.config.get("VAPID_PRIVATE_KEY"):
        logger.warning("push: VAPID_PRIVATE_KEY is not configured; skipping dispatch")
        return result

    # Use a fresh session. after_commit fires while the caller's session
    # is in 'committed' state and cannot emit any further SQL.
    try:
        sess = _fresh_session()
    except Exception:
        logger.exception("push: could not open fresh session")
        return result

    try:
        subscriptions = (
            sess.query(PushSubscription)
            .filter(PushSubscription.user_id == notification.recipient_id)
            .order_by(PushSubscription.created_at.desc())
            .all()
        )
        snapshots = [
            {
                "id": sub.id,
                "endpoint": sub.endpoint,
                "p256dh": sub.p256dh,
                "auth": sub.auth,
            }
            for sub in subscriptions
        ]
    except Exception:
        logger.exception("push: failed to query subscriptions")
        return result
    finally:
        sess.close()

    if not snapshots:
        return result

    cap = int(current_app.config.get("PUSH_MAX_PER_REQUEST", 50))
    timeout = int(current_app.config.get("PUSH_TIMEOUT_SECONDS", 5))

    if len(snapshots) > cap:
        result.skipped = len(snapshots) - cap
        logger.warning(
            "push: recipient=%s has %d subscriptions; capping at %d (skipped=%d)",
            notification.recipient_id, len(snapshots), cap, result.skipped,
        )
        snapshots = snapshots[:cap]

    payload = _build_payload(notification)

    for snap in snapshots:
        outcome = _send_snapshot(snap, payload, timeout)
        if outcome == "sent":
            result.sent += 1
        elif outcome == "deleted":
            result.deleted += 1
        else:
            result.failed += 1

    return result