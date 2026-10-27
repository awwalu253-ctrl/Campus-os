"""Task services — business logic shared by routes and scheduled tasks.

Phase 3.10. This module is called from `scripts/run_scheduled_work.py`
(Celery/Cron in production) and from the test suite. It contains no
Flask request-dependent code and no route decorators.
"""
from datetime import date, datetime, timedelta, timezone

from flask import url_for

from app.extensions import db
from app.notifications import services as notifications
from app.notifications import types as ntypes
from app.tasks.models import Task


# Tasks created before this date do not receive reminders. Bumped when
# we want a clean cutoff (e.g., after a backfill or after fixing a bug
# that caused widespread notifications). Set to the Phase 3.10 deploy
# date so pre-existing production tasks do not fire on first sweep.
TASK_REMINDERS_START_DATE = date(2026, 10, 27)


def send_task_reminders() -> dict:
    """Create reminder notifications for tasks due today or tomorrow.

    Eligibility (all must be true):
      - task.due_at is not None
      - task.completed_at is None
      - task.due_at >= today (UTC)
      - task.due_at <= tomorrow (UTC)
      - task.created_at >= TASK_REMINDERS_START_DATE (UTC midnight)

    Deduplication:
      Each reminder's dedupe_key is `task-reminder:{task.id}:{due_at}`.
      Re-running the sweep for the same (task, due_at) produces no new
      notification. Editing the task's due date produces a new key and
      a new reminder.

    Notification type is `TASK_REMINDER`, which is push-eligible — the
    existing `after_commit` listener will dispatch Web Push for each
    created notification.

    Does NOT commit per-notification. A single commit at the end.
    Rollback on exception. Safe to run concurrently with itself —
    `create_notification_if_new` uses ON CONFLICT DO NOTHING on the
    partial unique index, so concurrent runs create at most one row
    per (recipient_id, dedupe_key).

    Returns a dict: {"sent": int, "skipped": int, "candidates": int}.
      sent       — notifications actually inserted
      skipped    — candidates that already had a notification (dedupe hit)
      candidates — total tasks that passed the eligibility filter
    """
    now = datetime.now(timezone.utc)
    today = now.date()
    tomorrow = today + timedelta(days=1)

    # created_at is timezone-aware; TASK_REMINDERS_START_DATE is a date.
    # Compare created_at to midnight UTC on the start date.
    start_cutoff = datetime(
        TASK_REMINDERS_START_DATE.year,
        TASK_REMINDERS_START_DATE.month,
        TASK_REMINDERS_START_DATE.day,
        tzinfo=timezone.utc,
    )

    candidates = (
        Task.query
        .filter(Task.due_at.isnot(None))
        .filter(Task.completed_at.is_(None))
        .filter(Task.due_at >= today)
        .filter(Task.due_at <= tomorrow)
        .filter(Task.created_at >= start_cutoff)
        .all()
    )

    sent = 0
    skipped = 0

    for task in candidates:
        dedupe_key = f"task-reminder:{task.id}:{task.due_at.isoformat()}"

        result = notifications.create_notification_if_new(
            recipient_id=task.user_id,
            type=ntypes.TASK_REMINDER,
            title=f"Task due soon: {task.title}",
            body=(
                f"Your task '{task.title}' is due on "
                f"{task.due_at.strftime('%A, %B %d')}."
            ),
            action_url=url_for("tasks.edit", task_id=task.id),
            related_entity_type="task",
            related_entity_id=task.id,
            dedupe_key=dedupe_key,
        )

        if result is not None:
            sent += 1
        else:
            skipped += 1

    db.session.commit()

    return {
        "sent": sent,
        "skipped": skipped,
        "candidates": len(candidates),
    }