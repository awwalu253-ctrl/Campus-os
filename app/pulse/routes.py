from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.pulse import categories, services
from app.pulse.models import CampusReport

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
    return render_template(
        "pages/pulse/report_new.html",
        categories_by_group=categories.groups(),
        preset_location_id=request.args.get("location_id", ""),
    )


@bp.get("/report/<report_id>")
@login_required
def report_detail(report_id):
    report = services.get_report(report_id)
    if not report or report.moderation_status == "removed":
        abort(404)
    meta = categories.get(report.category)
    return render_template("pages/pulse/report_detail.html",
                           report=report, meta=meta)


@bp.post("/report/<report_id>/confirm")
@login_required
def confirm(report_id):
    report = services.get_report(report_id)
    if not report:
        abort(404)
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
    if not report:
        abort(404)
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
    if not report:
        abort(404)
    reason = request.form.get("reason", "").strip()
    try:
        services.flag_report(report=report, user=current_user, reason=reason)
        db.session.commit()
        flash("Report flagged. A moderator will review.", "info")
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "error")
    return redirect(url_for("pulse.report_detail", report_id=report_id))