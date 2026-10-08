from datetime import datetime, timezone

from flask import current_app
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy import event as sa_event
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.extensions import db
from app.notifications import types as ntypes
from app.notifications.models import Notification


# ── Push dispatch policy ──────────────────────────────────
# Only these notification types trigger a Web Push delivery. All
# other types are in-app only. This is enforced at queue time, not
# at dispatch time, so no other type ever enters the queue.
_PUSH_ELIGIBLE_TYPES = frozenset({
    ntypes.CAMPUS_SAFETY_REPORT,
    ntypes.REPORT_CONFIRMATION_MILESTONE,
})


def _queue_push_for(notification: Notification) -> None:
    """Append a push-eligible notification to the session's pending
    push queue.

    The queue lives on ``db.session.info['_pending_pushes']`` and is
    drained by the ``after_commit`` listener once the caller commits.

    If the caller rolls back, the queue is discarded with the session
    and push is never attempted. This is what guarantees the
    "commit then push, never the other way around" ordering.
    """
    if notification.type not in _PUSH_ELIGIBLE_TYPES:
        return

    try:
        if not current_app:
            return
    except RuntimeError:
        return

    if not current_app.config.get("PUSH_ENABLED", True):
        return

    queue = db.session.info.setdefault("_pending_pushes", [])
    queue.append(notification)

@sa_event.listens_for(Session, "after_commit")
def _drain_push_queue(session) -> None:
    """After a successful commit, drain the pending-push queue.

    Runs once per session commit. Dispatches push for any queued
    notifications. Push failures are logged but never propagated — the
    notification is already committed and must not be affected by
    delivery problems.

    IMPORTANT: this listener runs *after* the commit has completed and
    the session is in 'committed' state. It must NOT attempt to write
    to the database through this session. Any persistence that push
    delivery needs (e.g. deleting a stale subscription) is committed
    by push.py using its own session transaction.
    """
    queue = session.info.pop("_pending_pushes", None)
    if not queue:
        return

    # Import lazily to avoid a circular import at module load time.
    from app.notifications import push as push_sender

    for notification in queue:
        try:
            result = push_sender.dispatch_for_notification(notification)
            if result.sent or result.deleted or result.failed or result.skipped:
                current_app.logger.info(
                    "push: dispatch notification=%s result=%s",
                    notification.id, result.as_dict(),
                )
        except Exception:
            # Absolute last resort. Never let push break the caller.
            current_app.logger.exception(
                "push: unhandled error dispatching notification=%s",
                notification.id,
            )


# ── Create ────────────────────────────────────────────────
def create_notification(
    *,
    recipient_id: str,
    type: str,
    title: str,
    body: str | None = None,
    action_url: str | None = None,
    campus_id: str | None = None,
    related_entity_type: str | None = None,
    related_entity_id: str | None = None,
    dedupe_key: str | None = None,
    expires_at: datetime | None = None,
) -> Notification:
    """Insert a new notification.

    Does NOT commit. Caller must commit.

    Raises ValueError if the type is not registered.
    """
    if not ntypes.is_valid(type):
        raise ValueError(f"Unknown notification type: {type}")

    notification = Notification(
        recipient_id=recipient_id,
        type=type,
        title=title.strip()[:160],
        body=(body or "").strip()[:500] or None,
        action_url=(action_url or "").strip()[:255] or None,
        campus_id=campus_id,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
        dedupe_key=(dedupe_key or "").strip()[:255] or None,
        expires_at=expires_at,
    )
    db.session.add(notification)
    db.session.flush()
    _queue_push_for(notification)
    return notification


def create_notification_if_new(
    *,
    recipient_id: str,
    type: str,
    title: str,
    body: str | None = None,
    action_url: str | None = None,
    campus_id: str | None = None,
    related_entity_type: str | None = None,
    related_entity_id: str | None = None,
    dedupe_key: str,
    expires_at: datetime | None = None,
) -> Notification | None:
    """Insert a notification, but only if the (recipient_id, dedupe_key)
    pair does not already exist.

    Uses INSERT ... ON CONFLICT DO NOTHING on the partial unique index
    uq_notifications_recipient_dedupe. This is race-safe: concurrent
    requests that try to insert the same dedupe key will see only one
    succeed.

    dedupe_key is REQUIRED for this function. Use create_notification()
    when a notification has no natural dedupe key.

    Does NOT commit. Caller must commit.

    Returns the created Notification, or None if the insert was skipped
    due to an existing row.
    """
    if not ntypes.is_valid(type):
        raise ValueError(f"Unknown notification type: {type}")

    if not dedupe_key or not dedupe_key.strip():
        raise ValueError("create_notification_if_new requires a non-empty dedupe_key")

    stmt = (
        pg_insert(Notification)
        .values(
            recipient_id=recipient_id,
            type=type,
            title=title.strip()[:160],
            body=(body or "").strip()[:500] or None,
            action_url=(action_url or "").strip()[:255] or None,
            campus_id=campus_id,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            dedupe_key=dedupe_key.strip()[:255],
            expires_at=expires_at,
        )
        .on_conflict_do_nothing(
            index_elements=["recipient_id", "dedupe_key"],
            index_where=Notification.dedupe_key.isnot(None),
        )
        .returning(Notification.id)
    )

    result = db.session.execute(stmt).first()
    if result is None:
        return None

    db.session.flush()
    notification = db.session.get(Notification, result[0])
    if notification is not None:
        _queue_push_for(notification)
    return notification


# ── Read ──────────────────────────────────────────────────
def get_user_notifications(
    user_id: str,
    *,
    limit: int = 20,
    before_created_at: datetime | None = None,
    before_id: str | None = None,
    unread_only: bool = False,
) -> list[Notification]:
    """Fetch notifications for a user, newest first.

    Cursor pagination: pass (before_created_at, before_id) from the last
    item of the previous page. Both values are used because created_at
    may not be unique across rapid inserts.
    """
    limit = min(max(limit, 1), 50)

    stmt = (
        select(Notification)
        .where(Notification.recipient_id == user_id)
        .where(Notification.dismissed_at.is_(None))
    )

    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))

    if before_created_at is not None and before_id is not None:
        stmt = stmt.where(
            or_(
                Notification.created_at < before_created_at,
                and_(
                    Notification.created_at == before_created_at,
                    Notification.id < before_id,
                ),
            )
        )

    stmt = stmt.order_by(
        Notification.created_at.desc(),
        Notification.id.desc(),
    ).limit(limit)

    return list(db.session.execute(stmt).scalars().all())


def get_unread_count(user_id: str) -> int:
    """Count unread, undismissed notifications for a user."""
    stmt = (
        select(func.count(Notification.id))
        .where(Notification.recipient_id == user_id)
        .where(Notification.read_at.is_(None))
        .where(Notification.dismissed_at.is_(None))
    )
    return db.session.execute(stmt).scalar_one()


def get_notification_for_user(notification_id: str, user_id: str) -> Notification | None:
    """Fetch a single notification, scoped to the given user.

    Returns None if the notification does not exist OR does not belong
    to the user. The caller must not distinguish between the two.
    """
    stmt = (
        select(Notification)
        .where(Notification.id == notification_id)
        .where(Notification.recipient_id == user_id)
    )
    return db.session.execute(stmt).scalar_one_or_none()


# ── Mutate ────────────────────────────────────────────────
def mark_notification_read(notification_id: str, user_id: str) -> bool:
    """Mark a single notification as read.

    Scoped to the given user. Returns True if a row was updated,
    False if the notification does not exist or belongs to another user.

    Idempotent: marking an already-read notification returns True
    without changing read_at, because the UPDATE matches the row.

    Does NOT commit. Caller must commit.
    """
    now = datetime.now(timezone.utc)
    stmt = (
        update(Notification)
        .where(Notification.id == notification_id)
        .where(Notification.recipient_id == user_id)
        .where(Notification.read_at.is_(None))
        .values(read_at=now)
    )
    result = db.session.execute(stmt)
    if result.rowcount > 0:
        return True

    exists = db.session.execute(
        select(Notification.id)
        .where(Notification.id == notification_id)
        .where(Notification.recipient_id == user_id)
    ).first()
    return exists is not None


def mark_all_notifications_read(user_id: str) -> int:
    """Mark all unread notifications for a user as read.

    Returns the number of rows updated.

    Does NOT commit. Caller must commit.
    """
    now = datetime.now(timezone.utc)
    stmt = (
        update(Notification)
        .where(Notification.recipient_id == user_id)
        .where(Notification.read_at.is_(None))
        .where(Notification.dismissed_at.is_(None))
        .values(read_at=now)
    )
    result = db.session.execute(stmt)
    return result.rowcount or 0


# ── Serialization (for the API layer) ─────────────────────
def serialize(n: Notification) -> dict:
    """Return the public JSON shape for a notification.

    Never exposes internal fields (dedupe_key, related_entity_id,
    dismissed_at, campus_id).
    """
    return {
        "id": n.id,
        "type": n.type,
        "title": n.title,
        "body": n.body,
        "action_url": n.action_url,
        "read_at": n.read_at.isoformat() if n.read_at else None,
        "created_at": n.created_at.isoformat() if n.created_at else None,
        "expires_at": n.expires_at.isoformat() if n.expires_at else None,
    }