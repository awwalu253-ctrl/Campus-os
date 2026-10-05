from flask import Blueprint, render_template
from flask_login import login_required

from app.core.permissions import requires, Perm
from app.models import User, University, Location
from app.pulse.models import CampusReport
from app.maps.models import LocationSuggestion

bp = Blueprint("admin", __name__, url_prefix="/admin")


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