
from app.extensions import db
from app.models.mixins import UUIDMixin, TimestampMixin


class StaffCampusAssignment(UUIDMixin, TimestampMixin, db.Model):
    __tablename__ = "staff_campus_assignments"

    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    campus_id = db.Column(
        db.String(36),
        db.ForeignKey("campuses.id", ondelete="CASCADE"),
        nullable=False,
    )

    assigned_by = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )

    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "campus_id",
            name="uq_staff_campus_assignment_user_campus",
        ),
        db.Index(
            "ix_staff_campus_assignments_campus_active",
            "campus_id",
            "is_active",
        ),
    )
