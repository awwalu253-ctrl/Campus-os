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


@bp.get("/<task_id>/edit")
@login_required
def edit(task_id):
    """Placeholder for Step 2's full edit implementation.

    Returns 404 for now — the real handler arrives in Step 2. This
    placeholder exists so the Edit links in pages/tasks/index.html can
    resolve during Step 1's tests without a BuildError."""
    abort(404)