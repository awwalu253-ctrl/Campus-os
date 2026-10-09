"""Admin blueprint.

Routes for the Campus OS administration UI.

Authorization is enforced server-side via @requires(Perm.ADMIN_VIEW) on
every route. Frontend role hints are cosmetic only.
"""
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, render_template
from flask_login import login_required
from sqlalchemy import func, select

from app.core.permissions import requires, Perm
from app.extensions import db
from app.models import User, University, Campus
from app.models.audit import AuditLog
from app.maps.models import Location, LocationSuggestion
from app.notifications.models import Notification, PushSubscription
from app.pulse.models import CampusReport


bp = Blueprint("admin", __name__, url_prefix="/admin")


# ── Helpers ───────────────────────────────────────────────
def _safe(fn, default=None):
    """Run a query helper; return (value, error_string_or_None).

    On success: (result, None)
    On exception: (default, str(exc)) and log the exception.

    This lets the dashboard distinguish a genuine zero from a failed
    query, and display an unavailable state instead of fabricating a
    number.
    """
    try:
        return fn(), None
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("admin dashboard: query failed")
        return default, str(exc)


def _placeholder(title: str):
    """Render a 'later phase' page inside the admin shell."""
    return render_template("pages/admin/_placeholder.html", page_title=title)


# ── Overview ──────────────────────────────────────────────
@bp.get("/")
@login_required
@requires(Perm.ADMIN_VIEW)
def dashboard():
    now = datetime.now(timezone.utc)
    cutoff_7 = now - timedelta(days=7)
    cutoff_30 = now - timedelta(days=30)

    # ── Users ───────────────────────────────────────────
    user_total, user_total_err = _safe(
        lambda: db.session.execute(
            select(func.count(User.id)).where(User.deleted_at.is_(None))
        ).scalar_one()
    )
    user_active_7, user_active_7_err = _safe(
        lambda: db.session.execute(
            select(func.count(User.id))
            .where(User.deleted_at.is_(None))
            .where(User.last_login_at.isnot(None))
            .where(User.last_login_at >= cutoff_7)
        ).scalar_one()
    )
    user_active_30, user_active_30_err = _safe(
        lambda: db.session.execute(
            select(func.count(User.id))
            .where(User.deleted_at.is_(None))
            .where(User.last_login_at.isnot(None))
            .where(User.last_login_at >= cutoff_30)
        ).scalar_one()
    )

    # ── Universities and campuses ───────────────────────
    uni_count, uni_err = _safe(
        lambda: db.session.execute(
            select(func.count(University.id))
        ).scalar_one()
    )
    campus_count, campus_err = _safe(
        lambda: db.session.execute(
            select(func.count(Campus.id))
        ).scalar_one()
    )

    # ── Locations ───────────────────────────────────────
    location_total, loc_total_err = _safe(
        lambda: db.session.execute(
            select(func.count(Location.id))
        ).scalar_one()
    )
    location_approved, loc_appr_err = _safe(
        lambda: db.session.execute(
            select(func.count(Location.id)).where(Location.status == "approved")
        ).scalar_one()
    )
    location_pending, loc_pend_err = _safe(
        lambda: db.session.execute(
            select(func.count(Location.id)).where(Location.status == "pending")
        ).scalar_one()
    )
    location_err = loc_total_err or loc_appr_err or loc_pend_err

    # ── Campus Pulse ────────────────────────────────────
    report_active, rep_active_err = _safe(
        lambda: db.session.execute(
            select(func.count(CampusReport.id)).where(CampusReport.status == "active")
        ).scalar_one()
    )
    report_expired, rep_exp_err = _safe(
        lambda: db.session.execute(
            select(func.count(CampusReport.id)).where(CampusReport.status == "expired")
        ).scalar_one()
    )
    report_flagged, rep_flag_err = _safe(
        lambda: db.session.execute(
            select(func.count(CampusReport.id)).where(CampusReport.flag_count > 0)
        ).scalar_one()
    )
    report_err = rep_active_err or rep_exp_err or rep_flag_err

    # Category breakdown — top 8 by count, all time
    def _category_rows():
        rows = db.session.execute(
            select(CampusReport.category, func.count(CampusReport.id))
            .group_by(CampusReport.category)
            .order_by(func.count(CampusReport.id).desc())
            .limit(8)
        ).all()
        return [{"category": r[0], "count": r[1]} for r in rows]

    category_breakdown, category_err = _safe(_category_rows, default=[])

    # ── Suggestions ─────────────────────────────────────
    suggestion_pending, sug_pend_err = _safe(
        lambda: db.session.execute(
            select(func.count(LocationSuggestion.id))
            .where(LocationSuggestion.status == "pending")
        ).scalar_one()
    )
    suggestion_approved_30, sug_appr_err = _safe(
        lambda: db.session.execute(
            select(func.count(LocationSuggestion.id))
            .where(LocationSuggestion.status == "approved")
            .where(LocationSuggestion.moderated_at.isnot(None))
            .where(LocationSuggestion.moderated_at >= cutoff_30)
        ).scalar_one()
    )
    suggestion_err = sug_pend_err or sug_appr_err

    # ── Notifications and push ──────────────────────────
    notification_total, notif_total_err = _safe(
        lambda: db.session.execute(
            select(func.count(Notification.id))
        ).scalar_one()
    )
    notification_unread, notif_unread_err = _safe(
        lambda: db.session.execute(
            select(func.count(Notification.id))
            .where(Notification.read_at.is_(None))
            .where(Notification.dismissed_at.is_(None))
        ).scalar_one()
    )
    push_sub_count, push_sub_err = _safe(
        lambda: db.session.execute(
            select(func.count(PushSubscription.id))
        ).scalar_one()
    )
    push_stale_count, push_stale_err = _safe(
        lambda: db.session.execute(
            select(func.count(PushSubscription.id))
            .where(PushSubscription.created_at < cutoff_30)
            .where(PushSubscription.last_success_at.is_(None))
        ).scalar_one()
    )
    notification_err = notif_total_err or notif_unread_err or push_sub_err or push_stale_err

    # ── Recent audit activity ───────────────────────────
    def _recent_audit():
        rows = (
            AuditLog.query
            .order_by(AuditLog.created_at.desc())
            .limit(10)
            .all()
        )
        return [
            {
                "action": a.action,
                "entity_type": a.entity_type,
                "entity_id": a.entity_id,
                "actor_id": a.actor_id,
                "created_at": a.created_at,
            }
            for a in rows
        ]

    recent_audit, audit_err = _safe(_recent_audit, default=[])

    return render_template(
        "pages/admin/dashboard.html",
        user_total=user_total,
        user_total_err=user_total_err,
        user_active_7=user_active_7,
        user_active_7_err=user_active_7_err,
        user_active_30=user_active_30,
        user_active_30_err=user_active_30_err,
        uni_count=uni_count,
        uni_err=uni_err,
        campus_count=campus_count,
        campus_err=campus_err,
        location_total=location_total,
        location_approved=location_approved,
        location_pending=location_pending,
        location_err=location_err,
        report_active=report_active,
        report_expired=report_expired,
        report_flagged=report_flagged,
        report_err=report_err,
        category_breakdown=category_breakdown,
        category_err=category_err,
        suggestion_pending=suggestion_pending,
        suggestion_approved_30=suggestion_approved_30,
        suggestion_err=suggestion_err,
        notification_total=notification_total,
        notification_unread=notification_unread,
        push_sub_count=push_sub_count,
        push_stale_count=push_stale_count,
        notification_err=notification_err,
        recent_audit=recent_audit,
        audit_err=audit_err,
    )


# ── Management pages (Phase 3 will replace these stubs) ────
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