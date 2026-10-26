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