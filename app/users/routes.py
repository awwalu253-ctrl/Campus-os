from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.users.forms import ProfileForm

bp = Blueprint("users", __name__, url_prefix="/me")


@bp.get("/profile")
@login_required
def profile():
    return render_template("pages/users/profile.html")


@bp.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.display_name = form.display_name.data.strip()
        current_user.phone = form.phone.data or None
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("users.profile"))
    return render_template("pages/users/edit_profile.html", form=form)