"""Task model for the student to-do list feature.

Phase 3.9A. A task is a private, user-owned to-do item with an optional
due date and a small priority vocabulary. No campus scoping, no sharing,
no recurrence, no notifications in this phase.
"""
from app.extensions import db
from app.models.mixins import UUIDMixin, TimestampMixin


TASK_PRIORITIES = ("low", "medium", "high")


class Task(UUIDMixin, TimestampMixin, db.Model):
    __tablename__ = "tasks"

    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.String(1000), nullable=True)

    due_at = db.Column(db.Date, nullable=True, index=True)

    priority = db.Column(db.String(16), nullable=False, default="medium")
    # One of TASK_PRIORITIES: low | medium | high.

    completed_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    # NULL = pending. Non-NULL = completed at that UTC timestamp.

    __table_args__ = (
        db.Index(
            "ix_tasks_user_completed_due",
            "user_id", "completed_at", "due_at",
        ),
    )

    def __repr__(self) -> str:
        return f"<Task {self.title!r} → {self.user_id}>"