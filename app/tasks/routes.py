"""Tasks blueprint — authenticated, owner-scoped CRUD.

Phase 3.9B. Every route requires login. Every task access filters by
(current_user.id, task_id) so ownership is enforced by the query itself.
Phase 3.9B Step 1 delivers `index` and `new` only — `edit`, `complete`,
`uncomplete`, `delete` arrive in later steps.
"""
from flask import (
    Blueprint, abort, flash, redirect, render_template, request, url_for,
)
from flask_login import current_user, login_required

from app.extensions import db
from app.tasks.forms import TaskForm
from app.tasks.models import Task
from datetime import datetime, timezone


bp = Blueprint("tasks", __name__, url_prefix="/tasks")


def _get_owned_task(task_id):
    """Return the task if it exists AND belongs to current_user, else 404.

    The user_id filter is part of the query so a cross-user access can
    never accidentally succeed.
    """
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first()
    if task is None:
        abort(404)
    return task


@bp.get("/")
@login_required
def index():
    show = (request.args.get("show") or "").strip()
    show_completed = show == "all"

    query = Task.query.filter_by(user_id=current_user.id)
    if not show_completed:
        query = query.filter(Task.completed_at.is_(None))

    # Order: pending-first (completed_at NULL sorts before non-NULL when
    # ordering by is_(None) descending), then by due date ascending with
    # nulls last, then newest created first as tiebreaker.
    tasks = query.order_by(
        Task.completed_at.is_(None).desc(),
        Task.due_at.is_(None).asc(),
        Task.due_at.asc(),
        Task.created_at.desc(),
    ).all()

    return render_template(
        "pages/tasks/index.html",
        tasks=tasks,
        show_completed=show_completed,
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    form = TaskForm()

    if form.validate_on_submit():
        task = Task(
            user_id=current_user.id,
            title=form.title.data.strip(),
            description=(form.description.data or "").strip() or None,
            due_at=form.due_at.data,
            priority=form.priority.data,
        )
        db.session.add(task)
        db.session.commit()
        flash("Task created.", "success")
        return redirect(url_for("tasks.index"))

    return render_template("pages/tasks/new.html", form=form)


@bp.route("/<task_id>/edit", methods=["GET", "POST"])
@login_required
def edit(task_id):
    """Combined view and edit page for a single task.

    GET  → renders the form pre-populated with the task's current values.
    POST → validates, updates, commits, redirects to the list.

    Ownership is enforced by _get_owned_task: a task belonging to
    another user is indistinguishable from a nonexistent one (404).
    """
    task = _get_owned_task(task_id)
    form = TaskForm(obj=task)

    if form.validate_on_submit():
        task.title = form.title.data.strip()
        task.description = (form.description.data or "").strip() or None
        task.due_at = form.due_at.data
        task.priority = form.priority.data
        db.session.commit()
        flash("Task updated.", "success")
        return redirect(url_for("tasks.index"))

    return render_template("pages/tasks/edit.html", form=form, task=task)



@bp.post("/<task_id>/complete")
@login_required
def complete(task_id):
    """Mark a task as complete. Idempotent — a second call for an
    already-completed task leaves the original timestamp untouched."""
    task = _get_owned_task(task_id)
    if task.completed_at is None:
        task.completed_at = datetime.now(timezone.utc)
        db.session.commit()
        flash("Task completed.", "success")
    return redirect(url_for("tasks.index"))


@bp.post("/<task_id>/uncomplete")
@login_required
def uncomplete(task_id):
    """Reopen a completed task. Idempotent — a second call for an
    already-pending task is a no-op."""
    task = _get_owned_task(task_id)
    if task.completed_at is not None:
        task.completed_at = None
        db.session.commit()
        flash("Task reopened.", "success")
    return redirect(url_for("tasks.index"))


@bp.post("/<task_id>/delete")
@login_required
def delete(task_id):
    """Permanently delete a task. No soft delete — the row is gone."""
    task = _get_owned_task(task_id)
    db.session.delete(task)
    db.session.commit()
    flash("Task deleted.", "info")
    return redirect(url_for("tasks.index"))