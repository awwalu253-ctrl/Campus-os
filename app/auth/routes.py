from urllib.parse import urlparse

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db, limiter
from app.auth.forms import RegisterForm, LoginForm, ForgotForm, ResetForm
from app.auth import services
from app.core.audit import log
from app.models import User

bp = Blueprint("auth", __name__, url_prefix="/auth")

ADMIN_ROLES = ("platform_admin", "campus_admin", "moderator")


def _safe_next(target: str | None) -> str | None:
    if not target:
        return None
    parsed = urlparse(target)
    if parsed.netloc or parsed.scheme:
        return None
    return target


def _post_login_redirect(user) -> str:
    """Admins never see student onboarding."""
    if user.role in ADMIN_ROLES:
        return url_for("admin.dashboard")
    if not user.has_onboarded:
        return url_for("universities.onboarding")
    return url_for("web.home")


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("20 per hour", methods=["POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("web.home"))
    form = RegisterForm()
    if form.validate_on_submit():
        existing = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if existing:
            flash("An account with that email already exists.", "error")
        else:
            user = services.create_user(
                email=form.email.data,
                password=form.password.data,
                display_name=form.display_name.data,
                phone=form.phone.data,
            )
            log(user.id, "user.register", "user", user.id)
            db.session.commit()
            login_user(user)
            return redirect(url_for("universities.onboarding"))
    return render_template("pages/auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("30 per hour", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("web.home"))
    form = LoginForm()
    if form.validate_on_submit():
        user = services.authenticate(form.email.data, form.password.data)
        if not user:
            flash("Invalid email or password.", "error")
        else:
            login_user(user, remember=form.remember.data)
            db.session.commit()
            nxt = _safe_next(request.args.get("next"))
            if nxt:
                return redirect(nxt)
            return redirect(_post_login_redirect(user))
    return render_template("pages/auth/login.html", form=form)


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    flash("Signed out.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/forgot", methods=["GET", "POST"])
@limiter.limit("10 per hour", methods=["POST"])
def forgot():
    form = ForgotForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user:
            token = services.issue_reset_token(user)
            reset_url = url_for("auth.reset", token=token, _external=True)
            # Phase 1: log the URL. Mail wiring lands when MAIL_* are configured.
            current_app.logger.info("Password reset URL for %s: %s", user.email, reset_url)
        flash("If that email exists, a reset link has been sent.", "info")
        return redirect(url_for("auth.login"))
    return render_template("pages/auth/forgot.html", form=form)


@bp.route("/reset/<token>", methods=["GET", "POST"])
def reset(token):
    user = services.consume_reset_token(token)
    if not user:
        flash("That reset link is invalid or has expired.", "error")
        return redirect(url_for("auth.forgot"))
    form = ResetForm()
    if form.validate_on_submit():
        services.set_password(user, form.password.data)
        log(user.id, "user.password_reset", "user", user.id)
        db.session.commit()
        flash("Password updated. Please sign in.", "info")
        return redirect(url_for("auth.login"))
    return render_template("pages/auth/reset.html", form=form, token=token)