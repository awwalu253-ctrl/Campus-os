"""Student-facing routes for Campus Events."""

from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    url_for,
)
from flask_login import current_user, login_required

from app.extensions import db
from app.events import services
from app.events.forms import EventForm
from app.events.models import CampusEvent, EventRSVP


bp = Blueprint("events", __name__, url_prefix="/events")

# Campus OS currently targets Nigerian universities.
# Nigerian local time is West Africa Time (UTC+1), with no DST.
WAT = timezone(timedelta(hours=1), name="WAT")
@bp.app_template_filter("event_wat")
def event_wat(value, fmt):
    """Format a stored UTC event datetime in Nigerian local time."""
    if value is None:
        return ""

    # Database drivers may return UTC datetimes without tzinfo.
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.astimezone(WAT).strftime(fmt)


def _require_student():
    """Restrict student-facing Events pages to student accounts."""
    if current_user.role != "student":
        abort(403)

    if not current_user.profile or not current_user.profile.campus_id:
        flash("Complete your campus profile before using Events.", "info")
        return False

    return True


def _get_owned_event(event_id):
    """Return an event owned by the current student, otherwise 404."""
    event = CampusEvent.query.filter_by(
        id=event_id,
        organizer_id=current_user.id,
    ).first()

    if event is None:
        abort(404)

    return event


def _get_visible_event(event_id):
    """Return a published campus event or the current user's own event."""
    event = db.session.get(CampusEvent, event_id)

    if event is None:
        abort(404)

    is_owner = event.organizer_id == current_user.id
    is_published_on_campus = (
        event.status == "published"
        and event.campus_id == current_user.profile.campus_id
    )

    if not is_owner and not is_published_on_campus:
        abort(404)

    return event


def _set_form_datetime_values(form, event):
    """Populate datetime-local fields using Nigerian local time."""
    starts_at = event.starts_at
    ends_at = event.ends_at

    # Some database drivers return UTC values without tzinfo.
    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=timezone.utc)

    if ends_at.tzinfo is None:
        ends_at = ends_at.replace(tzinfo=timezone.utc)

    form.starts_at.data = starts_at.astimezone(WAT).replace(tzinfo=None)
    form.ends_at.data = ends_at.astimezone(WAT).replace(tzinfo=None)

def _event_form_values(form):
    """Convert validated form data into service-layer arguments."""
    starts_at = form.starts_at.data.replace(tzinfo=WAT).astimezone(timezone.utc)
    ends_at = form.ends_at.data.replace(tzinfo=WAT).astimezone(timezone.utc)

    return {
        "title": form.title.data,
        "description": form.description.data,
        "category": form.category.data,
        "venue": form.venue.data,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "capacity": form.capacity.data,
    }


@bp.get("/")
@login_required
def index():
    if not _require_student():
        return redirect(url_for("users.profile"))

    events = services.published_events_for_user(current_user)

    return render_template(
        "pages/events/index.html",
        events=events,
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    if not _require_student():
        return redirect(url_for("users.profile"))

    form = EventForm()

    if form.validate_on_submit():
        try:
            event = services.create_event(
                user=current_user,
                **_event_form_values(form),
            )
            db.session.commit()

            flash("Event draft created.", "success")
            return redirect(
                url_for("events.edit", event_id=event.id)
            )

        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "warning")

    return render_template(
        "pages/events/create.html",
        form=form,
    )


@bp.get("/<event_id>")
@login_required
def detail(event_id):
    if not _require_student():
        return redirect(url_for("users.profile"))

    event = _get_visible_event(event_id)

    rsvp = EventRSVP.query.filter_by(
        event_id=event.id,
        user_id=current_user.id,
    ).first()

    return render_template(
        "pages/events/detail.html",
        event=event,
        rsvp=rsvp,
    )


@bp.route("/<event_id>/edit", methods=["GET", "POST"])
@login_required
def edit(event_id):
    if not _require_student():
        return redirect(url_for("users.profile"))

    event = _get_owned_event(event_id)
    form = EventForm()

    if form.validate_on_submit():
        try:
            services.update_event(
                event=event,
                user=current_user,
                **_event_form_values(form),
            )
            db.session.commit()

            flash("Event updated.", "success")
            return redirect(
                url_for("events.detail", event_id=event.id)
            )

        except PermissionError:
            db.session.rollback()
            abort(404)

        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "warning")

    elif not form.is_submitted():
        form.title.data = event.title
        form.description.data = event.description
        form.category.data = event.category
        form.venue.data = event.venue
        form.capacity.data = event.capacity
        _set_form_datetime_values(form, event)

    return render_template(
        "pages/events/edit.html",
        form=form,
        event=event,
    )


@bp.post("/<event_id>/submit")
@login_required
def submit(event_id):
    if not _require_student():
        return redirect(url_for("users.profile"))

    event = _get_owned_event(event_id)

    try:
        services.submit_event(
            event=event,
            user=current_user,
        )
        db.session.commit()
        flash("Event submitted for review.", "success")

    except PermissionError:
        db.session.rollback()
        abort(404)

    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "warning")

    return redirect(
        url_for("events.detail", event_id=event.id)
    )


@bp.post("/<event_id>/rsvp")
@login_required
def rsvp(event_id):
    if not _require_student():
        return redirect(url_for("users.profile"))

    try:
        services.rsvp_to_event(
            event_id=event_id,
            user=current_user,
        )
        db.session.commit()
        flash("You're registered for this event.", "success")

    except PermissionError:
        db.session.rollback()
        abort(404)

    except ValueError as exc:
        db.session.rollback()

        # Hide missing and cross-campus events.
        if str(exc) == "Event does not exist.":
            abort(404)

        flash(str(exc), "warning")

    return redirect(
        url_for("events.detail", event_id=event_id)
    )

@bp.post("/<event_id>/cancel-rsvp")
@login_required
def cancel_rsvp(event_id):
    if not _require_student():
        return redirect(url_for("users.profile"))

    try:
        services.cancel_rsvp(
            event_id=event_id,
            user=current_user,
        )
        db.session.commit()
        flash("Your registration has been cancelled.", "info")

    except PermissionError:
        db.session.rollback()
        abort(404)

    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "warning")

    return redirect(
        url_for("events.detail", event_id=event_id)
    )


@bp.get("/mine")
@login_required
def mine():
    if not _require_student():
        return redirect(url_for("users.profile"))

    events = services.my_created_events(current_user)

    return render_template(
        "pages/events/my_events.html",
        events=events,
    )


@bp.get("/registered")
@login_required
def registered():
    if not _require_student():
        return redirect(url_for("users.profile"))

    events = services.my_registered_events(current_user)

    return render_template(
        "pages/events/registered.html",
        events=events,
    )
