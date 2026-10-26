"""Tests for the Tasks feature (Phase 3.9B+C).

Step 1 coverage: index (list) and create. Later steps add edit,
complete, uncomplete, and delete tests.
"""
import uuid

import pytest

from app.auth import services as auth_services
from app.extensions import db
from app.models import User
from app.tasks.models import Task


def _login(client, user_id):
    with client.session_transaction() as s:
        s["_user_id"] = user_id
        s["_fresh"] = True


def _make_user(*, name="Task Test"):
    suffix = uuid.uuid4().hex[:8]
    u = auth_services.create_user(
        email=f"task-{suffix}@example.com",
        password="testpass1234",
        display_name=name,
    )
    db.session.commit()
    return u.id


def _make_task(*, user_id, title="Test task", **kwargs):
    task = Task(user_id=user_id, title=title, **kwargs)
    db.session.add(task)
    db.session.commit()
    return task.id


# ── Index (list) ──────────────────────────────────────────
def test_tasks_index_requires_auth(client):
    r = client.get("/tasks/")
    assert r.status_code == 302


def test_tasks_index_shows_only_own_tasks(app, client):
    with app.app_context():
        uid_a = _make_user(name="User A")
        uid_b = _make_user(name="User B")
        _make_task(user_id=uid_a, title="Task for user A")
        _make_task(user_id=uid_b, title="Task for user B")

    _login(client, uid_a)
    r = client.get("/tasks/")
    assert r.status_code == 200
    assert b"Task for user A" in r.data
    assert b"Task for user B" not in r.data


def test_tasks_index_empty_state(app, client):
    with app.app_context():
        uid = _make_user()

    _login(client, uid)
    r = client.get("/tasks/")
    assert r.status_code == 200
    assert b"You haven't added any tasks yet." in r.data
    assert b"Add your first task" in r.data


# ── Create ────────────────────────────────────────────────
def test_task_create_persists(app, client):
    with app.app_context():
        uid = _make_user()

    _login(client, uid)
    r = client.post("/tasks/new", data={
        "title": "Buy textbooks",
        "description": "Calculus and linear algebra",
        "due_at": "2026-11-15",
        "priority": "high",
    })
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/tasks/")

    with app.app_context():
        task = Task.query.filter_by(title="Buy textbooks").one()
        assert task.user_id == uid
        assert task.description == "Calculus and linear algebra"
        assert task.due_at is not None
        assert task.priority == "high"
        assert task.completed_at is None


def test_task_create_rejects_empty_title(app, client):
    with app.app_context():
        uid = _make_user()

    _login(client, uid)
    r = client.post("/tasks/new", data={
        "title": "",
        "priority": "medium",
    })
    # Renders the form again with an error.
    assert r.status_code == 200
    assert b"Title is required." in r.data

    with app.app_context():
        assert Task.query.count() == 0


def test_task_create_rejects_invalid_priority(app, client):
    with app.app_context():
        uid = _make_user()

    _login(client, uid)
    r = client.post("/tasks/new", data={
        "title": "Test",
        "priority": "URGENT",  # not in choices
    })
    # WTForms' SelectField rejects values not in choices.
    assert r.status_code == 200

    with app.app_context():
        assert Task.query.count() == 0


# ── Edit ──────────────────────────────────────────────────
def test_task_edit_renders_for_owner(app, client):
    with app.app_context():
        uid = _make_user()
        task_id = _make_task(
            user_id=uid,
            title="Original title",
            description="Original description",
            priority="high",
        )

    _login(client, uid)
    r = client.get(f"/tasks/{task_id}/edit")
    assert r.status_code == 200

    body = r.data
    # The form renders with the task's current values.
    assert b"Original title" in body
    assert b"Original description" in body


def test_task_edit_updates_fields(app, client):
    with app.app_context():
        uid = _make_user()
        task_id = _make_task(
            user_id=uid,
            title="Old title",
            priority="low",
        )

    _login(client, uid)
    r = client.post(f"/tasks/{task_id}/edit", data={
        "title": "New title",
        "description": "New description",
        "due_at": "2026-12-01",
        "priority": "high",
    })
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/tasks/")

    with app.app_context():
        task = Task.query.filter_by(id=task_id).one()
        assert task.title == "New title"
        assert task.description == "New description"
        assert task.due_at is not None
        assert task.priority == "high"


def test_task_edit_requires_ownership(app, client):
    with app.app_context():
        uid_a = _make_user(name="User A")
        uid_b = _make_user(name="User B")
        task_id = _make_task(user_id=uid_b, title="B's task")

    _login(client, uid_a)

    # GET → 404, no form rendered.
    r = client.get(f"/tasks/{task_id}/edit")
    assert r.status_code == 404

    # POST → 404, task not modified.
    r = client.post(f"/tasks/{task_id}/edit", data={
        "title": "Hijacked",
        "priority": "high",
    })
    assert r.status_code == 404

    with app.app_context():
        task = Task.query.filter_by(id=task_id).one()
        assert task.title == "B's task"  # unchanged




# ── Complete ──────────────────────────────────────────────
def test_task_complete_sets_timestamp(app, client):
    with app.app_context():
        uid = _make_user()
        task_id = _make_task(user_id=uid, title="Pending task")

    _login(client, uid)
    r = client.post(f"/tasks/{task_id}/complete")
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/tasks/")

    with app.app_context():
        task = Task.query.filter_by(id=task_id).one()
        assert task.completed_at is not None


def test_task_complete_is_idempotent(app, client):
    with app.app_context():
        uid = _make_user()
        task_id = _make_task(user_id=uid, title="Task")

    _login(client, uid)
    client.post(f"/tasks/{task_id}/complete")

    with app.app_context():
        first_completed_at = Task.query.filter_by(id=task_id).one().completed_at

    # Second call should not change the timestamp.
    client.post(f"/tasks/{task_id}/complete")

    with app.app_context():
        second_completed_at = Task.query.filter_by(id=task_id).one().completed_at

    assert first_completed_at == second_completed_at


# ── Uncomplete ────────────────────────────────────────────
def test_task_uncomplete_clears_timestamp(app, client):
    with app.app_context():
        uid = _make_user()
        task_id = _make_task(user_id=uid, title="Completed task")
        # Pre-complete it directly.
        from datetime import datetime, timezone
        task = Task.query.filter_by(id=task_id).one()
        task.completed_at = datetime.now(timezone.utc)
        db.session.commit()

    _login(client, uid)
    r = client.post(f"/tasks/{task_id}/uncomplete")
    assert r.status_code == 302

    with app.app_context():
        task = Task.query.filter_by(id=task_id).one()
        assert task.completed_at is None


# ── Delete ────────────────────────────────────────────────
def test_task_delete_removes_task(app, client):
    with app.app_context():
        uid = _make_user()
        task_id = _make_task(user_id=uid, title="Doomed task")

    _login(client, uid)
    r = client.post(f"/tasks/{task_id}/delete")
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/tasks/")

    with app.app_context():
        assert Task.query.filter_by(id=task_id).first() is None


def test_task_delete_requires_ownership(app, client):
    with app.app_context():
        uid_a = _make_user(name="User A")
        uid_b = _make_user(name="User B")
        task_id = _make_task(user_id=uid_b, title="Task owned by B")

    _login(client, uid_a)
    r = client.post(f"/tasks/{task_id}/delete")
    assert r.status_code == 404

    with app.app_context():
        # Task not deleted — user A could not touch user B's row.
        assert Task.query.filter_by(id=task_id).first() is not None