from flask import Blueprint, render_template
from flask_login import login_required

from app.core.permissions import requires, Perm
from app.models import User, University
from app.maps.models import Location
from app.pulse.models import CampusReport
from app.maps.models import LocationSuggestion

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _placeholder(title: str):
    """Render a 'coming in a later phase' page inside the admin shell."""
    return render_template("pages/admin/_placeholder.html", page_title=title)


@bp.get("/")
@login_required
@requires(Perm.ADMIN_VIEW)
def dashboard():
    return render_template(
        "pages/admin/dashboard.html",
        user_count=User.query.count(),
        uni_count=University.query.count(),
        location_count=Location.query.count(),
        active_report_count=CampusReport.query.filter_by(status="active").count(),
        pending_suggestion_count=LocationSuggestion.query.filter_by(status="pending").count(),
        flagged_report_count=CampusReport.query.filter(CampusReport.flag_count > 0).count(),
    )


# ── Stubs (Phase 3 replaces each with a real page) ────────
@bp.get("/users")
@login_required
@requires(Perm.ADMIN_VIEW)
def users_list():
    return _placeholder("Users")


@bp.get("/universities")
@login_required
@requires(Perm.ADMIN_VIEW)
def universities_list():
    return _placeholder("Universities")


@bp.get("/locations")
@login_required
@requires(Perm.ADMIN_VIEW)
def locations_list():
    return _placeholder("Locations")


@bp.get("/pulse")
@login_required
@requires(Perm.ADMIN_VIEW)
def pulse_list():
    return _placeholder("Campus Pulse")


@bp.get("/suggestions")
@login_required
@requires(Perm.ADMIN_VIEW)
def suggestions_list():
    return _placeholder("Location suggestions")


@bp.get("/notifications")
@login_required
@requires(Perm.ADMIN_VIEW)
def notifications_overview():
    return _placeholder("Notifications")


@bp.get("/analytics")
@login_required
@requires(Perm.ADMIN_VIEW)
def analytics():
    return _placeholder("Analytics")


@bp.get("/audit")
@login_required
@requires(Perm.ADMIN_VIEW)
def audit_list():
    return _placeholder("Audit logs")


@bp.get("/health")
@login_required
@requires(Perm.ADMIN_VIEW)
def health():
    return _placeholder("System health")