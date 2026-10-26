"""Tests for the Task model (Phase 3.9A).

Covers the model's structural guarantees without any routes existing yet:
  1. Defaults: new task gets priority='medium', completed_at=None,
     created_at populated, UUID id.
  2. FK cascade: deleting the owning user deletes the task.
  3. Vocabulary: TASK_PRIORITIES is exactly ('low', 'medium', 'high').

Route, form, and template behaviour will be tested in Phase 3.9B+.
"""
import uuid
from datetime import date

from app.auth import services as auth_services
from app.extensions import db
from app.models import User
from app.tasks.models import Task, TASK_PRIORITIES


def _make_user():
    """Create a test user via the auth service, commit, return the id."""
    suffix = uuid.uuid4().hex[:8]
    u = auth_services.create_user(
        email=f"task-{suffix}@example.com",
        password="testpass1234",
        display_name="Task Test",
    )
    db.session.commit()
    return u.id


# ── 1. Defaults ───────────────────────────────────────────
def test_task_defaults(app):
    with app.app_context():
        uid = _make_user()

        task = Task(user_id=uid, title="Test task")
        db.session.add(task)
        db.session.commit()

        # Primary key: a 36-char UUID string.
        assert isinstance(task.id, str)
        assert len(task.id) == 36

        # Defaults applied at insert time.
        assert task.priority == "medium"
        assert task.completed_at is None
        assert task.description is None
        assert task.due_at is None

        # Timestamp mixins populated.
        assert task.created_at is not None
        assert task.updated_at is not None


# ── 2. FK cascade on user delete ──────────────────────────
def test_task_cascade_deleted_with_user(app):
    with app.app_context():
        uid = _make_user()

        task = Task(user_id=uid, title="Doomed task")
        db.session.add(task)
        db.session.commit()
        task_id = task.id

        # Sanity: the task exists.
        assert db.session.get(Task, task_id) is not None

        # Delete the owning user.
        user = db.session.get(User, uid)
        db.session.delete(user)
        db.session.commit()

        # FK CASCADE should have removed the task.
        assert db.session.get(Task, task_id) is None


# ── 3. Priority vocabulary ────────────────────────────────
def test_task_priority_vocabulary():
    """The tuple of valid priorities is locked in. A change to this
    tuple is a deliberate schema/vocabulary decision that should come
    with form/template updates."""
    assert TASK_PRIORITIES == ("low", "medium", "high")