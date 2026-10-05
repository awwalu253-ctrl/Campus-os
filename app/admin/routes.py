from flask import Blueprint, render_template
from flask_login import login_required

from app.core.permissions import requires, Perm

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.get("/")
@login_required
@requires(Perm.ADMIN_VIEW)
def dashboard():
    from app.models import User, University
    return render_template(
        "pages/admin/dashboard.html",
        user_count=User.query.count(),
        uni_count=University.query.count(),
    )