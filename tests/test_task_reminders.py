"""Tests for the task reminder sweep (Phase 3.10 Step 2).

All tests run against an isolated test database (`campusos_test`) with
`PUSH_ENABLED=False`. No real push notifications are dispatched.

Every fixture commits explicitly so the test client's request cycle
sees the same DB state the sweep sees.
"""
import uuid
from datetime import date, datetime, timedelta, timezone

from app.auth import services as auth_services
from app.extensions import db
from app.models import User
from app.notifications.models import Notification
from app.notifications import types as ntypes
from app.tasks.models import Task
from app.tasks.services import send_task_reminders, TASK_REMINDERS_START_DATE


def _make_user(*, name="Task Test"):
    suffix = uuid.uuid4().hex[:8]
    u = auth_services.create_user(
        email=f"task-reminder-{suffix}@example.com",
        password="testpass1234",
        display_name=name,
    )
    db.session.commit()
    return u.id


def _make_task(*, user_id, title="Test task", due_at, completed_at=None,
               created_at=None):
    """Create a Task with explicit due_at/completed_at/created_at.

    If created_at is None, the model's default (now) is used.
    """
    task = Task(
        user_id=user_id,
        title=title,
        due_at=due_at,
        completed_at=completed_at,
    )
    if created_at is not None:
        task.created_at = created_at
    db.session.add(task)
    db.session.commit()
    return task.id


def _today():
    return datetime.now(timezone.utc).date()


def _tomorrow():
    return _today() + timedelta(days=1)


def _notification_count(user_id):
    return Notification.query.filter_by(
        recipient_id=user_id, type=ntypes.TASK_REMINDER,
    ).count()


# ── 1. Task due today → notified ──────────────────────────
def test_reminder_creates_notification_for_due_today(app):
    with app.app_context():
        uid = _make_user()
        _make_task(user_id=uid, title="Due today", due_at=_today())

        result = send_task_reminders()
        assert result["sent"] == 1
        assert result["skipped"] == 0
        assert _notification_count(uid) == 1

        n = Notification.query.filter_by(
            recipient_id=uid, type=ntypes.TASK_REMINDER,
        ).one()
        assert n.title == "Task due soon: Due today"
        assert "Due today" in n.body
        assert "due on" in n.body


# ── 2. Task due tomorrow → notified ───────────────────────
def test_reminder_creates_notification_for_due_tomorrow(app):
    with app.app_context():
        uid = _make_user()
        _make_task(user_id=uid, title="Due tomorrow", due_at=_tomorrow())

        result = send_task_reminders()
        assert result["sent"] == 1
        assert _notification_count(uid) == 1


# ── 3. Task due in 3 days → not notified ──────────────────
def test_reminder_skips_task_due_in_three_days(app):
    with app.app_context():
        uid = _make_user()
        far = _today() + timedelta(days=3)
        _make_task(user_id=uid, title="Far future", due_at=far)

        result = send_task_reminders()
        assert result["sent"] == 0
        assert result["candidates"] == 0
        assert _notification_count(uid) == 0


# ── 4. Task due yesterday → not notified ──────────────────
def test_reminder_skips_overdue_task(app):
    with app.app_context():
        uid = _make_user()
        past = _today() - timedelta(days=1)
        _make_task(user_id=uid, title="Overdue", due_at=past)

        result = send_task_reminders()
        assert result["sent"] == 0
        assert _notification_count(uid) == 0


# ── 5. Completed task → not notified ──────────────────────
def test_reminder_skips_completed_task(app):
    with app.app_context():
        uid = _make_user()
        _make_task(
            user_id=uid,
            title="Already done",
            due_at=_today(),
            completed_at=datetime.now(timezone.utc),
        )

        result = send_task_reminders()
        assert result["sent"] == 0
        assert _notification_count(uid) == 0


# ── 6. Task with no due date → not notified ───────────────
def test_reminder_skips_task_without_due_date(app):
    with app.app_context():
        uid = _make_user()
        # due_at=None; due_at.isnot(None) filter excludes it.
        _make_task(user_id=uid, title="Someday", due_at=None)

        result = send_task_reminders()
        assert result["sent"] == 0
        assert _notification_count(uid) == 0


# ── 7. Idempotency ────────────────────────────────────────
def test_reminder_is_idempotent(app):
    with app.app_context():
        uid = _make_user()
        _make_task(user_id=uid, title="Due today", due_at=_today())

        first = send_task_reminders()
        assert first["sent"] == 1
        assert first["skipped"] == 0

        second = send_task_reminders()
        assert second["sent"] == 0
        assert second["skipped"] == 1
        assert _notification_count(uid) == 1


# ── 8. Ownership: only A's task reminded, not B's ─────────
def test_reminder_respects_ownership(app):
    with app.app_context():
        uid_a = _make_user(name="User A")
        uid_b = _make_user(name="User B")
        _make_task(user_id=uid_a, title="A's task", due_at=_today())
        _make_task(user_id=uid_b, title="B's task", due_at=_today())

        send_task_reminders()

        assert _notification_count(uid_a) == 1
        assert _notification_count(uid_b) == 1

        # A's reminder is addressed to A, not B.
        notif_a = Notification.query.filter_by(
            recipient_id=uid_a, type=ntypes.TASK_REMINDER,
        ).one()
        assert notif_a.recipient_id == uid_a


# ── 9. Changed due date → second reminder ────────────────
def test_reminder_creates_new_for_changed_due_date(app):
    with app.app_context():
        uid = _make_user()
        task_id = _make_task(
            user_id=uid, title="Movable task", due_at=_today(),
        )

        send_task_reminders()
        assert _notification_count(uid) == 1

        # Change due date to tomorrow. This changes the dedupe key.
        task = Task.query.filter_by(id=task_id).one()
        task.due_at = _tomorrow()
        db.session.commit()

        # Sweep again — new due_at → new dedupe key → new notification.
        result = send_task_reminders()
        assert result["sent"] == 1
        assert _notification_count(uid) == 2


# ── 10. Task created before cutoff → not notified ────────
def test_reminder_ignores_task_created_before_start_date(app):
    with app.app_context():
        uid = _make_user()
        # Simulate a task created before the cutoff.
        old_created_at = datetime(
            TASK_REMINDERS_START_DATE.year,
            TASK_REMINDERS_START_DATE.month,
            TASK_REMINDERS_START_DATE.day - 1,
            tzinfo=timezone.utc,
        )
        _make_task(
            user_id=uid,
            title="Pre-cutoff task",
            due_at=_today(),
            created_at=old_created_at,
        )

        result = send_task_reminders()
        assert result["sent"] == 0
        assert result["candidates"] == 0
        assert _notification_count(uid) == 0