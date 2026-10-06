from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.core.permissions import requires, Perm
from app.maps import categories as loc_cats
from app.maps import services
from app.maps.models import LocationSuggestion
from app.pulse import services as pulse_services

bp = Blueprint("maps", __name__, url_prefix="/map")

STAFF_ROLES = ("platform_admin", "campus_admin", "moderator")


def _campus_id():
    """Return the current user's campus.

    Students use their profile's campus. Staff roles (admin/moderator) have
    no StudentProfile, so they fall back to the first campus in the system —
    enough for previewing the map without a full onboarding flow.
    """
    if not current_user.is_authenticated:
        return None

    if current_user.profile and current_user.profile.campus_id:
        return current_user.profile.campus_id

    if current_user.role in STAFF_ROLES:
        from app.models import Campus
        first = Campus.query.order_by(Campus.name).first()
        if first:
            return first.id

    return None


def _staff_without_campus():
    """True when a staff user has no campus to fall back to (nothing seeded)."""
    return (
        current_user.is_authenticated
        and current_user.role in STAFF_ROLES
        and not (current_user.profile and current_user.profile.campus_id)
    )


@bp.get("/")
@login_required
def index():
    campus_id = _campus_id()
    if not campus_id:
        if _staff_without_campus():
            flash("No campus data seeded yet. Run the seed scripts first.", "info")
            return redirect(url_for("admin.dashboard"))
        flash("Complete your campus setup first.", "info")
        return redirect(url_for("universities.onboarding"))

    return render_template(
        "pages/map/index.html",
        categories=loc_cats.all_categories(),
    )


@bp.get("/api/locations")
@login_required
def api_locations():
    campus_id = _campus_id()
    if not campus_id:
        return jsonify({"error": "no campus"}), 400

    category = request.args.get("category") or None
    search = request.args.get("q") or None

    features = services.approved_locations_geo(
        campus_id, category=category, search=search,
    )
    return jsonify({"locations": features})


@bp.get("/api/pulse")
@login_required
def api_pulse():
    """Active Pulse reports as map markers, joined to locations in one go."""
    campus_id = _campus_id()
    if not campus_id:
        return jsonify({"error": "no campus"}), 400

    reports = pulse_services.active_reports_for_campus(campus_id, limit=200)

    location_ids = [r.location_id for r in reports if r.location_id]
    coords_by_loc: dict[str, tuple[float, float]] = {}
    if location_ids:
        from app.maps.models import Location
        from sqlalchemy import select, func
        rows = db.session.execute(
            select(
                Location.id,
                func.ST_Y(Location.point),
                func.ST_X(Location.point),
            ).where(Location.id.in_(location_ids))
        ).all()
        coords_by_loc = {row[0]: (row[1], row[2]) for row in rows}

    out = []
    for r in reports:
        if not r.location_id:
            continue
        latlng = coords_by_loc.get(r.location_id)
        if not latlng:
            continue
        lat, lng = latlng
        out.append({
            "id": r.id,
            "category": r.category,
            "confidence": r.confidence,
            "description": r.description,
            "lat": float(lat) if lat is not None else None,
            "lng": float(lng) if lng is not None else None,
            "reported_at": r.reported_at.isoformat(),
            "url": url_for("pulse.report_detail", report_id=r.id),
        })
    return jsonify({"reports": out})


@bp.route("/suggest", methods=["GET", "POST"])
@login_required
def suggest():
    campus_id = _campus_id()
    if not campus_id:
        flash("Complete your campus setup first.", "info")
        return redirect(url_for("universities.onboarding"))

    if request.method == "POST":
        try:
            name = request.form["name"].strip()
            category = request.form["category"].strip()
            lat = float(request.form["lat"])
            lng = float(request.form["lng"])
            description = request.form.get("description", "").strip()

            services.suggest_location(
                campus_id=campus_id, user_id=current_user.id,
                name=name, category=category, lat=lat, lng=lng,
                description=description,
            )
            db.session.commit()
            flash("Thanks — your suggestion is pending review.", "success")
            return redirect(url_for("maps.index"))
        except (KeyError, ValueError) as e:
            db.session.rollback()
            flash(f"Invalid input: {e}", "error")

    return render_template(
        "pages/map/suggest.html",
        categories=loc_cats.all_categories(),
    )


# ── Admin moderation ──────────────────────────────────────
@bp.get("/admin/suggestions")
@login_required
@requires(Perm.ADMIN_VIEW)
def admin_suggestions():
    items = services.pending_suggestions()
    return render_template("pages/map/admin_suggestions.html", suggestions=items)


@bp.post("/admin/suggestions/<sug_id>/approve")
@login_required
@requires(Perm.ADMIN_VIEW)
def admin_approve(sug_id):
    sug = db.session.get(LocationSuggestion, sug_id)
    if not sug:
        abort(404)
    try:
        services.approve_suggestion(sug, moderator_id=current_user.id)
        db.session.commit()
        flash("Approved.", "success")
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "error")
    return redirect(url_for("maps.admin_suggestions"))


@bp.post("/admin/suggestions/<sug_id>/reject")
@login_required
@requires(Perm.ADMIN_VIEW)
def admin_reject(sug_id):
    sug = db.session.get(LocationSuggestion, sug_id)
    if not sug:
        abort(404)
    try:
        services.reject_suggestion(sug, moderator_id=current_user.id,
                                   note=request.form.get("note", ""))
        db.session.commit()
        flash("Rejected.", "info")
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "error")
    return redirect(url_for("maps.admin_suggestions"))


@bp.get("/location/<location_id>")
@login_required
def location_detail(location_id):
    loc = services.get_location(location_id)
    if not loc or loc.status != "approved":
        abort(404)
    geo = services.as_geojson(loc)
    from app.pulse.models import CampusReport
    reports = (CampusReport.query
               .filter_by(location_id=loc.id, status="active")
               .order_by(CampusReport.reported_at.desc())
               .limit(20).all())
    return render_template("pages/map/location_detail.html",
                           location=loc, geo=geo, reports=reports)