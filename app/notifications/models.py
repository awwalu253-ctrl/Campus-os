from app.extensions import db
from app.models.mixins import UUIDMixin, TimestampMixin


class Notification(UUIDMixin, TimestampMixin, db.Model):
    """A single user-facing notification.

    Notifications are addressed to exactly one recipient. Campus-scoped
    notifications are fanned out at write time (one row per recipient)
    rather than represented as a shared row with a join table.

    Types are application-level strings declared in app.notifications.types.
    """

    __tablename__ = "notifications"

    recipient_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Application-level type key. See app.notifications.types.REGISTRY.
    type = db.Column(db.String(48), nullable=False, index=True)

    title = db.Column(db.String(160), nullable=False)
    body = db.Column(db.String(500), nullable=True)

    # Optional in-app link. Should be a relative path (e.g. "/pulse/report/<id>").
    action_url = db.Column(db.String(255), nullable=True)

    # Optional campus scope. Nullable for user-specific notifications that
    # have no campus context. SET NULL on campus deletion so history survives.
    campus_id = db.Column(
        db.String(36),
        db.ForeignKey("campuses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Loose reference to the entity that produced the notification (e.g.
    # "campus_report", "location_suggestion"). No FK constraint — the
    # notification is historical fact even if the referenced entity is
    # later deleted.
    related_entity_type = db.Column(db.String(32), nullable=True)
    related_entity_id = db.Column(db.String(36), nullable=True, index=True)

    # Dedupe key. Used with a partial unique index to prevent the same
    # logical notification from being created twice for the same recipient.
    # Nullable — some notification types have no natural dedupe key.
    dedupe_key = db.Column(db.String(255), nullable=True)

    read_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    dismissed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # Fast "my notifications, newest first" query.
        db.Index(
            "ix_notifications_recipient_created",
            "recipient_id",
            "created_at",
        ),
        # Fast unread count. Partial index keeps it small.
        db.Index(
            "ix_notifications_recipient_unread",
            "recipient_id",
            postgresql_where=db.text("read_at IS NULL AND dismissed_at IS NULL"),
        ),
        # Fast "notifications for this campus" query.
        db.Index(
            "ix_notifications_campus_created",
            "campus_id",
            "created_at",
        ),
        # Database-level dedupe protection. Only applies when a dedupe_key
        # is present; allows any number of notifications with NULL dedupe_key.
        db.Index(
            "uq_notifications_recipient_dedupe",
            "recipient_id",
            "dedupe_key",
            unique=True,
            postgresql_where=db.text("dedupe_key IS NOT NULL"),
        ),
    )

    def __repr__(self) -> str:
        return f"<Notification {self.type} → {self.recipient_id}>"