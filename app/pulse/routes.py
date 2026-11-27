from flask import (
    Blueprint, render_template, redirect, url_for, flash,
    request, abort, current_app,
)
from flask_login import login_required, current_user

from app.extensions import db
from app.pulse import categories, services
from app.pulse.models import CampusReport
from app.maps.models import Location
from sqlalchemy import func, select

bp = Blueprint("pulse", __name__, url_prefix="/pulse")


STAFF_ROLES = ("platform_admin", "campus_admin", "moderator")


def _current_campus_id() -> str:
    """Return the current user's campus.

    Students use their profile's campus. Staff roles (admin/moderator)
    have no StudentProfile, so they fall back to the first campus in the
    system — enough to view and moderate Pulse without a full student
    onboarding.
    """
    if current_user.profile and current_user.profile.campus_id:
        return current_user.profile.campus_id

    if current_user.role in STAFF_ROLES:
        from app.models import Campus
        first = Campus.query.order_by(Campus.name).first()
        if first:
            return first.id

    return None


def _is_staff() -> bool:
    return current_user.role in ("platform_admin", "campus_admin", "moderator")


def _ensure_report_accessible(report) -> None:
    """Abort 404 if the report is unreachable for the current user.

    Rules (Batch 1):
      - Missing report              -> 404
      - Cross-campus                -> 404 (campus isolation)
      - moderation_status="removed" -> 404 (any user)
      - moderation_status="hidden"  -> 404 unless staff
    """
    if report is None:
        abort(404)
    if report.campus_id != _current_campus_id():
        abort(404)
    if report.moderation_status == "removed":
        abort(404)
    if report.moderation_status == "hidden" and not _is_staff():
        abort(404)


def _get_unique_valid_general_campus_area(campus_id: str) -> Location | None:
    """Return the single valid General Campus Area for this campus, or None.

    "Valid" means:
      - campus_id matches
      - name == "General Campus Area"
      - status == "approved"
      - point is not NULL and not empty (ST_IsEmpty is false)

    Duplicate handling:
      - 0 valid matches  -> None (caller falls back to location_id=None)
      - 1 valid match    -> that Location
      - >1 valid matches -> None and log a warning; never pick arbitrarily,
                            never delete, never modify.
    """
    rows = db.session.execute(
        select(
            Location.id,
            Location.name,
            func.ST_Y(Location.point).label("lat"),
            func.ST_X(Location.point).label("lng"),
            func.ST_IsEmpty(Location.point).label("is_empty"),
        )
        .where(Location.campus_id == campus_id)
        .where(Location.name == "General Campus Area")
        .where(Location.status == "approved")
    ).all()

    valid = [
        row for row in rows
        if row.lat is not None
        and row.lng is not None
        and not bool(row.is_empty)
    ]

    if len(valid) == 0:
        return None

    if len(valid) > 1:
        current_app.logger.warning(
            "Duplicate General Campus Area locations for campus %s: %s. "
            "Leaving location_id=None; do not auto-select or modify.",
            campus_id,
            [str(row.id) for row in valid],
        )
        return None

    return db.session.get(Location, valid[0].id)


@bp.get("/")
@login_required
def index():
    campus_id = _current_campus_id()
    if not campus_id:
        flash("Complete your campus setup first.", "info")
        return redirect(url_for("universities.onboarding"))
    reports = services.active_reports_for_campus(campus_id, limit=50)
    return render_template("pages/pulse/index.html",
                           reports=reports,
                           categories_by_group=categories.groups())


@bp.route("/report/new", methods=["GET", "POST"])
@login_required
def report_new():
    campus_id = _current_campus_id()
    if not campus_id:
        flash("Complete your campus setup first.", "info")
        return redirect(url_for("universities.onboarding"))

    if request.method == "POST":
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()

        if not categories.is_valid(category):
            flash("Please pick a category.", "error")
            return render_template(
                "pages/pulse/report_new.html",
                categories_by_group=categories.groups(),
                preset_location_id=request.form.get("location_id", ""),
            )

        location_id = request.form.get("location_id", "").strip() or None
        user_supplied_location = location_id is not None

        # Step 2: if the user didn't pick a location, default to the
        # campus's General Campus Area (when provisioned and valid).
        # Missing / duplicate / invalid GCA -> stays None (Decision A1).
        # No coordinates invented. api_pulse() still filters out any
        # legacy NULL-location reports (Decision B1, unchanged).
        if location_id is None:
            gc = _get_unique_valid_general_campus_area(campus_id)
            if gc is not None:
                location_id = gc.id

        # Step 4: validate user-supplied location (not the Step 2 default).
        if user_supplied_location:
            loc = db.session.get(Location, location_id)
            if (
                loc is None
                or loc.campus_id != campus_id
                or loc.status != "approved"
            ):
                flash(
                    "That location isn't available on your campus.",
                    "error",
                )
                return render_template(
                    "pages/pulse/report_new.html",
                    categories_by_group=categories.groups(),
                    preset_location_id="",
                    available_locations=(
                        Location.query
                        .filter_by(campus_id=campus_id, status="approved")
                        .order_by(Location.name)
                        .all()
                    ),
                    general_campus_area_id=(
                        _get_unique_valid_general_campus_area(campus_id).id
                        if _get_unique_valid_general_campus_area(campus_id)
                        else None
                    ),
                    form_category=category,
                    form_description=description,
                )

        report = services.create_report(
            user=current_user,
            campus_id=campus_id,
            category=category,
            description=description,
            location_id=location_id,
        )
        db.session.commit()
        flash("Report posted.", "success")
        return redirect(url_for("pulse.report_detail", report_id=report.id))

    # GET
    from app.maps.models import Location as _Loc  # local alias, not needed at top
    available_locations = (
        _Loc.query
        .filter_by(campus_id=campus_id, status="approved")
        .order_by(_Loc.name)
        .all()
    )

    gca = _get_unique_valid_general_campus_area(campus_id)
    general_campus_area_id = gca.id if gca is not None else None

    raw_preset = request.args.get("location_id", "").strip()
    preset_location_id = ""
    if raw_preset:
        if general_campus_area_id and raw_preset == general_campus_area_id:
            preset_location_id = raw_preset
        elif any(loc.id == raw_preset for loc in available_locations):
            preset_location_id = raw_preset

    return render_template(
        "pages/pulse/report_new.html",
        categories_by_group=categories.groups(),
        preset_location_id=preset_location_id,
        available_locations=available_locations,
        general_campus_area_id=general_campus_area_id,
    )


@bp.get("/report/<report_id>")
@login_required
def report_detail(report_id):
    report = services.get_report(report_id)
    _ensure_report_accessible(report)
    meta = categories.get(report.category)
    return render_template("pages/pulse/report_detail.html",
                           report=report, meta=meta)


@bp.post("/report/<report_id>/confirm")
@login_required
def confirm(report_id):
    report = services.get_report(report_id)
    _ensure_report_accessible(report)
    try:
        services.confirm_report(report=report, user=current_user)
        db.session.commit()
        flash("Confirmed.", "success")
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "error")
    return redirect(url_for("pulse.report_detail", report_id=report_id))


@bp.post("/report/<report_id>/disagree")
@login_required
def disagree(report_id):
    report = services.get_report(report_id)
    _ensure_report_accessible(report)
    try:
        services.disagree_report(report=report, user=current_user)
        db.session.commit()
        flash("Disagreement recorded.", "info")
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "error")
    return redirect(url_for("pulse.report_detail", report_id=report_id))


@bp.post("/report/<report_id>/flag")
@login_required
def flag(report_id):
    report = services.get_report(report_id)
    _ensure_report_accessible(report)
    reason = request.form.get("reason", "").strip()
    try:
        services.flag_report(report=report, user=current_user, reason=reason)
        db.session.commit()
        flash("Report flagged. A moderator will review.", "info")
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "error")
    return redirect(url_for("pulse.report_detail", report_id=report_id))