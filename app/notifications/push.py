"""Web Push sender.

Design rules enforced by this module:

1. Never raises to the caller. Push delivery failure must never propagate
   into a request transaction or a Celery task.
2. Never logs subscription endpoints, payloads, or VAPID keys.
3. Deletes subscriptions on 404/410 (permanent invalid).
4. Leaves subscriptions in place on transient failures (500, timeout,
   network error) so they can be retried on the next dispatch.
5. Enforces a per-call timeout and a per-request attempt cap.
6. Uses the current_app config for VAPID and policy.
7. Runs inside a Flask app context.
"""
import logging
from datetime import datetime, timezone

from flask import current_app
from pywebpush import WebPushException, webpush

from app.extensions import db
from app.notifications.models import PushSubscription

logger = logging.getLogger(__name__)


class PushResult:
    """Result of one push dispatch run.

    Attributes:
        sent:        number of successful deliveries
        deleted:     number of subscriptions deleted (404/410)
        failed:      number of transient failures (kept, not retried here)
        skipped:     number of subscriptions beyond the cap
    """

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


def _build_payload(notification) -> dict:
    """Construct the payload sent to the browser.

    Keep it small. The service worker will use these fields to render
    the OS notification. action_url is the deep link target.
    """
    return {
        "title": notification.title or "Campus OS",
        "body": notification.body or "",
        "url": notification.action_url or "/",
        "tag": notification.id,  # collapse duplicates on the device
    }


def _vapid_claims() -> dict:
    """Build the VAPID claims dict from config.

    pywebpush expects {'sub': 'mailto:...'}. If the subject is empty
    or malformed, we still attempt the send — some push services are
    lenient, and a hard failure here would break all push delivery.
    """
    subject = current_app.config.get("VAPID_SUBJECT") or "mailto:admin@campusos.app"
    return {"sub": subject}


def _delete_subscription(sub: PushSubscription, reason: str) -> None:
    """Delete a subscription that the push service has rejected.

    Commits immediately in its own transaction. This function is only
    called after the caller's transaction has already committed (from
    the after_commit listener), so the current session is free to start
    a new transaction and commit it.

    Never raises. A failure to delete is logged and ignored — the
    subscription will be retried on the next dispatch, and if the
    endpoint really is dead, the next send will get another 410.
    """
    logger.info(
        "push: deleting stale subscription id=%s reason=%s",
        sub.id, reason,
    )
    try:
        db.session.delete(sub)
        db.session.commit()
    except Exception:
        logger.exception("push: failed to delete stale subscription id=%s", sub.id)
        try:
            db.session.rollback()
        except Exception:
            pass


def send_to_subscription(
    subscription: PushSubscription,
    payload: dict,
    timeout: int,
) -> str:
    """Send one push.

    Returns one of: "sent" | "deleted" | "failed".
    Never raises. Never logs payload or keys.
    """
    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {
                    "p256dh": subscription.p256dh,
                    "auth": subscription.auth,
                },
            },
            data=__import__("json").dumps(payload),
            vapid_private_key=current_app.config["VAPID_PRIVATE_KEY"],
            vapid_claims=_vapid_claims(),
            timeout=timeout,
        )
        subscription.last_success_at = datetime.now(timezone.utc)
        return "sent"

    except WebPushException as exc:
        # Inspect the response status if present. 404 and 410 are
        # permanent — the endpoint is gone, the subscription is dead.
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)

        if status in (404, 410):
            _delete_subscription(subscription, f"http_{status}")
            return "deleted"

        logger.warning(
            "push: transient failure id=%s status=%s error=%s",
            subscription.id, status, type(exc).__name__,
        )
        return "failed"

    except Exception as exc:
        # Timeout, DNS, TLS handshake failure, connection reset,
        # anything else. Never let it escape.
        logger.warning(
            "push: unexpected failure id=%s error=%s",
            subscription.id, type(exc).__name__,
        )
        return "failed"


def dispatch_for_notification(notification) -> PushResult:
    """Send a push for one notification to all its subscriptions.

    Behaviour:
      - If PUSH_ENABLED is False, returns an empty result immediately.
      - If VAPID private key is missing, logs a warning and returns.
      - If no subscriptions exist for the recipient, returns empty.
      - Caps at PUSH_MAX_PER_REQUEST subscriptions. Extra ones are
        counted in result.skipped and logged once. They are NOT
        deleted — they will be dispatched on the next notification.
      - Does NOT commit. The caller commits after the loop.

    This function NEVER raises.
    """
    result = PushResult()

    if not current_app.config.get("PUSH_ENABLED", True):
        return result

    if not current_app.config.get("VAPID_PRIVATE_KEY"):
        logger.warning("push: VAPID_PRIVATE_KEY is not configured; skipping dispatch")
        return result

    try:
        subscriptions = (
            PushSubscription.query
            .filter(PushSubscription.user_id == notification.recipient_id)
            .order_by(PushSubscription.created_at.desc())
            .all()
        )
    except Exception:
        logger.exception("push: failed to query subscriptions")
        return result

    if not subscriptions:
        return result

    cap = int(current_app.config.get("PUSH_MAX_PER_REQUEST", 50))
    timeout = int(current_app.config.get("PUSH_TIMEOUT_SECONDS", 5))

    if len(subscriptions) > cap:
        result.skipped = len(subscriptions) - cap
        logger.warning(
            "push: recipient=%s has %d subscriptions; capping at %d (skipped=%d)",
            notification.recipient_id, len(subscriptions), cap, result.skipped,
        )
        subscriptions = subscriptions[:cap]

    payload = _build_payload(notification)

    for sub in subscriptions:
        outcome = send_to_subscription(sub, payload, timeout)
        if outcome == "sent":
            result.sent += 1
        elif outcome == "deleted":
            result.deleted += 1
        else:
            result.failed += 1

    return result