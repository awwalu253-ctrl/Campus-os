from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.pulse import services as pulse_services

bp = Blueprint("web", __name__)


@bp.get("/")
def landing():
    if current_user.is_authenticated:
        return home()
    return render_template("pages/landing.html")


@bp.get("/home")
@login_required
def home():
    campus_id = None
    if current_user.profile:
        campus_id = current_user.profile.campus_id

    live_reports = []
    if campus_id:
        live_reports = pulse_services.live_home_preview(campus_id, limit=3)

    return render_template("pages/home.html", live_reports=live_reports)