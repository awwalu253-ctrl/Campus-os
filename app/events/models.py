
from app.extensions import db
from app.models.mixins import UUIDMixin, TimestampMixin


EVENT_STATUSES = (
    "draft",
    "pending_review",
    "published",
    "rejected",
)


class CampusEvent(UUIDMixin, TimestampMixin, db.Model):
    __tablename__ = "campus_events"

    campus_id = db.Column(
        db.String(36),
        db.ForeignKey("campuses.id", ondelete="CASCADE"),
        nullable=False,
    )

    organizer_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.String(3000), nullable=False)
    category = db.Column(db.String(32), nullable=False)
    venue = db.Column(db.String(180), nullable=False)

    starts_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    ends_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
    )

    capacity = db.Column(db.Integer, nullable=True)

    status = db.Column(
        db.String(24),
        nullable=False,
        default="draft",
    )

    reviewed_by = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    rejection_reason = db.Column(db.String(1000), nullable=True)
    published_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Relationships
    campus = db.relationship("Campus")

    organizer = db.relationship(
        "User",
        foreign_keys=[organizer_id],
    )

    reviewer = db.relationship(
        "User",
        foreign_keys=[reviewed_by],
    )

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('draft', 'pending_review', 'published', 'rejected')",
            name="ck_campus_events_status",
        ),
        db.CheckConstraint(
            "ends_at > starts_at",
            name="ck_campus_events_valid_time_range",
        ),
        db.CheckConstraint(
            "capacity IS NULL OR capacity > 0",
            name="ck_campus_events_positive_capacity",
        ),
        db.Index(
            "ix_campus_events_campus_status_start",
            "campus_id",
            "status",
            "starts_at",
        ),
        db.Index(
            "ix_campus_events_status_created",
            "status",
            "created_at",
        ),
    )


class EventRSVP(UUIDMixin, TimestampMixin, db.Model):
    __tablename__ = "event_rsvps"

    event_id = db.Column(
        db.String(36),
        db.ForeignKey("campus_events.id", ondelete="CASCADE"),
        nullable=False,
    )

    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        db.UniqueConstraint(
            "event_id",
            "user_id",
            name="uq_event_rsvp_event_user",
        ),
    )
