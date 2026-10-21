from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.users.forms import ProfileForm

bp = Blueprint("users", __name__, url_prefix="/me")


@bp.get("/profile")
@login_required
def profile():
    """Profile page. Read-only display of the student's academic placement.

    The university and campus are set during onboarding and are not
    editable from this page. Both are shown as text (with the
    university's state) so a student can confirm which campus their
    account is attached to. Em dashes render when a value is missing.
    """
    university = None
    campus = None

    if current_user.profile:
        from app.models import University, Campus

        if current_user.profile.university_id:
            university = db.session.get(University, current_user.profile.university_id)

        if current_user.profile.campus_id:
            campus = db.session.get(Campus, current_user.profile.campus_id)

    return render_template(
        "pages/users/profile.html",
        university=university,
        campus=campus,
    )


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