from app.extensions import db
from app.models.mixins import UUIDMixin, TimestampMixin, utcnow


REPORT_STATUS = ("active", "stale", "expired", "removed")


class CampusReport(UUIDMixin, TimestampMixin, db.Model):
    __tablename__ = "campus_reports"

    campus_id = db.Column(db.String(36), db.ForeignKey("campuses.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    location_id = db.Column(db.String(36), db.ForeignKey("locations.id", ondelete="SET NULL"),
                            nullable=True, index=True)
    category = db.Column(db.String(48), nullable=False, index=True)
    status = db.Column(db.String(16), nullable=False, default="active", index=True)

    description = db.Column(db.String(500), nullable=True)
    image_key = db.Column(db.String(255), nullable=True)

    reported_by = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"),
                            nullable=True, index=True)
    reported_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)

    # Derived — never set from user input
    confidence = db.Column(db.String(16), nullable=False, default="low")
    confirmation_count = db.Column(db.Integer, nullable=False, default=0)
    disagreement_count = db.Column(db.Integer, nullable=False, default=0)
    flag_count = db.Column(db.Integer, nullable=False, default=0)

    moderation_status = db.Column(db.String(16), nullable=False, default="visible")
    # visible | hidden | removed

    __table_args__ = (
        db.Index("ix_reports_campus_status_expires",
                 "campus_id", "status", "expires_at"),
    )


class ReportConfirmation(UUIDMixin, TimestampMixin, db.Model):
    __tablename__ = "report_confirmations"

    report_id = db.Column(db.String(36), db.ForeignKey("campus_reports.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    kind = db.Column(db.String(16), nullable=False)  # confirm | disagree

    __table_args__ = (
        db.UniqueConstraint("report_id", "user_id", name="uq_confirmation_per_user_per_report"),
    )


class ReportFlag(UUIDMixin, TimestampMixin, db.Model):
    __tablename__ = "report_flags"

    report_id = db.Column(db.String(36), db.ForeignKey("campus_reports.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"),
                        nullable=True, index=True)
    reason = db.Column(db.String(120), nullable=True)

    __table_args__ = (
        db.UniqueConstraint("report_id", "user_id", name="uq_flag_per_user_per_report"),
    )