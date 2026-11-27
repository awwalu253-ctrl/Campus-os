"""Staff moderation routes for Campus Events."""

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from app.core.permissions import Perm, requires
from app.events import services
from app.extensions import db
from zoneinfo import ZoneInfo


admin_bp = Blueprint(
    "event_admin",
    __name__,
    url_prefix="/admin/events",
)


@admin_bp.get("/")
@login_required
@requires(Perm.ADMIN_VIEW)
def review_queue():
    campus_id = request.args.get("campus_id") or None

    try:
        events = services.review_queue(
            current_user,
            campus_id=campus_id,
        )
    except PermissionError:
        abort(404)

    return render_template(
        "pages/admin/events_review.html",
        events=events,
        campus_id=campus_id,
    )


@admin_bp.get("/<event_id>")
@login_required
@requires(Perm.ADMIN_VIEW)
def detail(event_id):
    try:
        event = services.get_event_for_review(
            event_id=event_id,
            reviewer=current_user,
        )
    except (LookupError, PermissionError):
        abort(404)
    except ValueError:
        flash("This event is no longer awaiting review.", "info")
        return redirect(url_for("event_admin.review_queue"))

    return render_template(
        "pages/admin/event_review_detail.html",
        event=event,
    )


@admin_bp.post("/<event_id>/approve")
@login_required
@requires(Perm.ADMIN_VIEW)
def approve(event_id):
    try:
        event = services.get_event_for_review(
            event_id=event_id,
            reviewer=current_user,
        )
        services.approve_event(
            event=event,
            reviewer=current_user,
        )
        db.session.commit()
    except (LookupError, PermissionError):
        db.session.rollback()
        abort(404)
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")
        return redirect(url_for("event_admin.review_queue"))
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Event approval failed.")
        flash("Could not approve this event. Please try again.", "error")
        return redirect(url_for("event_admin.review_queue"))

    flash("Event approved and published.", "success")
    return redirect(url_for("event_admin.review_queue"))


@admin_bp.post("/<event_id>/reject")
@login_required
@requires(Perm.ADMIN_VIEW)
def reject(event_id):
    reason = request.form.get("reason", "")

    try:
        event = services.get_event_for_review(
            event_id=event_id,
            reviewer=current_user,
        )
        services.reject_event(
            event=event,
            reviewer=current_user,
            reason=reason,
        )
        db.session.commit()
    except (LookupError, PermissionError):
        db.session.rollback()
        abort(404)
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "error")
        return redirect(
            url_for("event_admin.detail", event_id=event_id)
        )
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Event rejection failed.")
        flash("Could not reject this event. Please try again.", "error")
        return redirect(
            url_for("event_admin.detail", event_id=event_id)
        )
    
    flash("Event rejected.", "success")
    return redirect(url_for("event_admin.review_queue"))