"""Admin blueprint.

Routes for the Campus OS administration UI.

Authorization is enforced server-side via @requires(Perm.ADMIN_VIEW) on
every route. Frontend role hints are cosmetic only.
"""
from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint, abort, current_app, flash, redirect, render_template,
    request, url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func, select, text

from app.core import audit as audit_log
from app.core.permissions import requires, Perm
from app.extensions import db
from app.models import User, University, Campus
from app.models.audit import AuditLog
from app.maps import categories as loc_cats
from app.maps.models import Location, LocationSuggestion
from app.notifications.models import Notification, PushSubscription
from app.pulse import categories as pulse_categories
from app.pulse import moderation as pulse_moderation
from app.pulse.models import CampusReport, ReportConfirmation, ReportFlag


bp = Blueprint("admin", __name__, url_prefix="/admin")

USERS_PER_PAGE = 25


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


def _placeholder(title: str, *, section_icon: str | None = None, teaser: str | None = None):
    """Render a 'later phase' page inside the admin shell.

    section_icon — one of the recognised keys in the placeholder template's
                   inline icon macro ('users', 'universities', 'locations',
                   'pulse', 'suggestions', 'notifications', 'analytics',
                   'audit', 'health'). Unknown/None falls back to a generic
                   "not yet built" glyph.
    teaser       — one short sentence describing the section's planned scope.
    """
    return render_template(
        "pages/admin/_placeholder.html",
        page_title=title,
        section_icon=section_icon,
        teaser=teaser,
    )


# ── Audit helpers ─────────────────────────────────────────
AUDIT_PER_PAGE = 50

# Human-readable titles for the actions we know about. Unknown
# actions fall back to a title-cased dotted-string rendering so
# a new action still shows sensibly without a code change.
_ACTION_LABELS = {
    "user.suspend": "User suspended",
    "user.restore": "User restored",
    "pulse.hide": "Report hidden",
    "pulse.remove": "Report removed",
    "pulse.restore": "Report restored",
}


def _action_label(action: str) -> str:
    """Human-friendly label for an audit action identifier."""
    if action in _ACTION_LABELS:
        return _ACTION_LABELS[action]
    return action.replace(".", " ").replace("_", " ").strip().title()


def _audit_summary(entry: AuditLog) -> str:
    """One-line, human-readable summary of a before/after change.

    Only emits a summary when both sides are dicts and they share
    at least one key whose values differ. Otherwise returns an
    em dash, so the table never shows a misleading arrow.
    """
    before = entry.before if isinstance(entry.before, dict) else None
    after = entry.after if isinstance(entry.after, dict) else None
    if not before or not after:
        return "—"

    parts = []
    for key in sorted(set(before) | set(after)):
        b = before.get(key)
        a = after.get(key)
        if b == a:
            continue
        parts.append(f"{key}: {b} → {a}")

    return "; ".join(parts) if parts else "—"


def _parse_page(raw) -> int:
    """Parse a page number from a query-string value.

    Returns 1 for None, empty, non-integer, or values below 1.
    Accepts only ASCII digits (optionally with surrounding
    whitespace), which rejects "abc", "1.5", "-3", "1,000".
    """
    if raw is None:
        return 1
    text = str(raw).strip()
    if not text.isdigit():
        return 1
    value = int(text)
    return value if value >= 1 else 1


def _parse_iso_date(value: str | None):
    """Parse a YYYY-MM-DD date from a form/query param.

    Returns a timezone-aware UTC datetime at midnight, or None on
    empty/invalid input. Invalid input is silently ignored rather
    than 500'ing, matching how filters behave elsewhere on the
    admin surface.
    """
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


# ── Suggestion helpers ────────────────────────────────────
SUGGESTIONS_PER_PAGE = 25

_STATUS_PILL_CLASS = {
    "pending": "amber",
    "approved": "green",
    "rejected": "red",
}


def _category_label(key: str | None) -> str:
    """Human-readable label for a location category key.

    Falls back to the raw key when the value is unknown, so a
    suggestion with a stale category still renders sensibly.
    """
    if not key:
        return "—"
    meta = loc_cats.LOCATION_CATEGORIES.get(key)
    if meta:
        return meta.get("label", key)
    return key


def _status_pill(status: str | None) -> str:
    """CSS modifier for the status pill; defaults to gray."""
    if not status:
        return "gray"
    return _STATUS_PILL_CLASS.get(status, "gray")


def _bulk_resolve(rows) -> dict:
    """Resolve campus and user FKs for a list of suggestion rows.

    Returns a dict with three lookup tables keyed by id:
      {
        "campuses":      {campus_id: Campus},
        "users":         {user_id: User},
        "locations":     {location_id: Location},
      }

    Any id that doesn't resolve is simply absent from the dict;
    the template renders an em dash for those cases.
    """
    campus_ids = {r.campus_id for r in rows if r.campus_id}
    user_ids = set()
    location_ids = set()
    for r in rows:
        if r.proposed_by:
            user_ids.add(r.proposed_by)
        if r.moderated_by:
            user_ids.add(r.moderated_by)
        if r.approved_location_id:
            location_ids.add(r.approved_location_id)

    campuses = {}
    if campus_ids:
        campuses = {
            c.id: c for c in Campus.query.filter(Campus.id.in_(campus_ids)).all()
        }

    users = {}
    if user_ids:
        users = {
            u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()
        }

    locations = {}
    if location_ids:
        locations = {
            l.id: l for l in Location.query.filter(Location.id.in_(location_ids)).all()
        }

    return {"campuses": campuses, "users": users, "locations": locations}


# ── Pulse helpers ─────────────────────────────────────────
PULSE_PER_PAGE = 25

_MODERATION_PILL_CLASS = {
    "visible": "green",
    "hidden":  "amber",
    "removed": "red",
}


def _pulse_status_pill(status: str | None) -> str:
    """CSS modifier for the lifecycle status pill."""
    if status == "active":
        return "green"
    if status == "expired":
        return "gray"
    if status == "removed":
        return "red"
    if status == "stale":
        return "amber"
    return "gray"


def _moderation_pill(moderation_status: str | None) -> str:
    """CSS modifier for the moderation-status pill."""
    return _MODERATION_PILL_CLASS.get(moderation_status or "", "gray")


def _pulse_category_label(key: str | None) -> str:
    """Human label for a Pulse category key, with safe fallback."""
    if not key:
        return "—"
    meta = pulse_categories.get(key)
    if meta:
        return meta.get("label", key)
    return key


def _bulk_resolve_pulse(rows) -> dict:
    """Resolve user and campus FKs for a list of CampusReport rows.

    Returns:
      {
        "users":     {user_id: User},
        "campuses":  {campus_id: Campus},
        "locations": {location_id: Location},
      }
    Missing ids are simply absent; the template renders an em dash.
    """
    user_ids = set()
    campus_ids = set()
    location_ids = set()
    for r in rows:
        if r.reported_by:
            user_ids.add(r.reported_by)
        if r.campus_id:
            campus_ids.add(r.campus_id)
        if r.location_id:
            location_ids.add(r.location_id)

    users = {}
    if user_ids:
        users = {u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()}

    campuses = {}
    if campus_ids:
        campuses = {
            c.id: c for c in Campus.query.filter(Campus.id.in_(campus_ids)).all()
        }

    locations = {}
    if location_ids:
        locations = {
            l.id: l for l in Location.query.filter(Location.id.in_(location_ids)).all()
        }

    return {"users": users, "campuses": campuses, "locations": locations}

# ── System health helpers ─────────────────────────────────
# Every helper returns {"status": <label>, "message": <safe text>} and
# never raises. The health page renders whatever comes back; a failed
# check is shown as a red/amber/gray pill, not as a 500 response. No
# helper ever puts exception text, credentials, connection strings, or
# config values into the response.

# ── Notifications helpers ─────────────────────────────────
# Read-only metrics for the admin Notifications & Push page.
# Every helper returns a plain value or a small dict; none raise.
# No helper touches PushSubscription.endpoint, p256dh, auth, or
# Notification.dedupe_key — those are never surfaced to the admin.

# Reuse the same stale-subscription definition as the Overview page:
# created more than 30 days ago and never successfully delivered.
STALE_PUSH_DAYS = 30
ACTIVE_PUSH_DAYS = 7


def _notification_type_label(key: str | None) -> str:
    """Human label for a notification type key.

    Uses the canonical registry from app.notifications.types. Falls
    back to the raw key so an unregistered type still renders sensibly.
    """
    if not key:
        return "—"
    from app.notifications import types as ntypes
    meta = ntypes.meta(key)
    if meta:
        return meta.get("label", key)
    return key


def _notification_type_category(key: str | None) -> str:
    """Category string for a notification type key ('pulse', 'locations')."""
    if not key:
        return "—"
    from app.notifications import types as ntypes
    meta = ntypes.meta(key)
    if meta:
        return meta.get("category", "—")
    return "—"


def _bulk_resolve_recipients(rows) -> dict:
    """Resolve recipient_id FKs for a list of Notification rows.

    Returns {"users": {user_id: User}}. Missing ids are absent;
    the template renders a short id prefix for those cases.
    """
    recipient_ids = {r.recipient_id for r in rows if r.recipient_id}
    users = {}
    if recipient_ids:
        users = {
            u.id: u for u in User.query.filter(User.id.in_(recipient_ids)).all()
        }
    return {"users": users}


def _bulk_resolve_subscription_users(rows) -> dict:
    """Resolve user_id FKs for a list of PushSubscription rows.

    Same shape as _bulk_resolve_recipients.
    """
    user_ids = {s.user_id for s in rows if s.user_id}
    users = {}
    if user_ids:
        users = {
            u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()
        }
    return {"users": users}


def _shorten_ua(user_agent: str | None, *, max_len: int = 60) -> str:
    """Compact display for a User-Agent string.

    The full string is preserved by the caller via a title= attribute;
    this helper only shortens it for the table cell. Returns an em dash
    when the value is missing.
    """
    if not user_agent:
        return "—"
    ua = user_agent.strip()
    if len(ua) <= max_len:
        return ua
    return ua[:max_len - 1] + "…"


# ── Location helpers ──────────────────────────────────────
LOCATIONS_PER_PAGE = 25

_LOCATION_STATUS_PILL = {
    "approved": "green",
    "pending":  "amber",
    "rejected": "red",
}

_LOCATION_SOURCE_LABEL = {
    "student": "Student submission",
    "admin":   "Admin entry",
}


def _location_status_pill(status: str | None) -> str:
    """CSS modifier for a Location.status pill."""
    return _LOCATION_STATUS_PILL.get(status or "", "gray")


def _location_source_label(source: str | None) -> str:
    """Human-readable label for a Location.source value."""
    if not source:
        return "—"
    return _LOCATION_SOURCE_LABEL.get(source, source)


def _bulk_resolve_locations(rows) -> dict:
    """Resolve campus and user FKs for a list of Location rows.

    Returns {"campuses": {id: Campus}, "users": {id: User}}.
    Location FKs used: campus_id, created_by, verified_by.
    Missing ids are absent; the template renders an em dash.
    """
    campus_ids = {r.campus_id for r in rows if r.campus_id}
    user_ids = set()
    for r in rows:
        if r.created_by:
            user_ids.add(r.created_by)
        if r.verified_by:
            user_ids.add(r.verified_by)

    campuses = {}
    if campus_ids:
        campuses = {
            c.id: c for c in Campus.query.filter(Campus.id.in_(campus_ids)).all()
        }

    users = {}
    if user_ids:
        users = {
            u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()
        }

    return {"campuses": campuses, "users": users}


def _check_db() -> dict:
    """Database liveness via a trivial SELECT.

    Uses the same probe as /healthz/deps: SELECT 1 through the SQLAlchemy
    session. Any exception is swallowed and reported as 'error' with a
    generic message — the exception text may contain the connection
    string or credentials, so it must not reach the page.
    """
    try:
        db.session.execute(text("SELECT 1"))
        return {"status": "ok", "message": "Connected."}
    except Exception:
        current_app.logger.exception("health: database check failed")
        return {"status": "error", "message": "Database query failed."}


def _check_redis() -> dict:
    """Redis reachability via a PING.

    Independent of Celery: this checks the Redis instance the app uses
    for rate limiting and general cache purposes. Celery may be
    configured against a different broker and is checked separately.
    """
    redis_url = current_app.config.get("REDIS_URL") or ""
    if not redis_url:
        return {"status": "not_configured", "message": "Redis URL is not configured."}

    try:
        import redis as _redis
        client = _redis.from_url(redis_url, socket_timeout=2)
        client.ping()
        return {"status": "ok", "message": "Connected."}
    except Exception:
        current_app.logger.exception("health: redis check failed")
        return {"status": "error", "message": "Redis is unreachable."}


def _check_celery() -> dict:
    """Celery worker reachability via the broker's inspect ping.

    Deliberately independent of _check_redis: the Celery broker URL is
    a separate configuration value (CELERY_BROKER_URL) and may point at
    a different Redis instance or database than REDIS_URL.

    Four distinct states are reported, none of which is fabricated:
      - unknown      — the broker is 'memory://' (in-process, unreachable
                       from this process by any external worker), or the
                       check itself cannot be performed.
      - broker_error — the broker is configured but unreachable.
      - no_workers   — the broker responded, but no workers replied.
      - ok           — one or more workers replied to the ping.

    Uses a bare Celery client built from the broker URL rather than
    importing tasks.celery_app.celery. The latter would trigger a full
    create_app() call at import time inside the request thread; the
    bare client achieves the same inspect broadcast without that cost.
    """
    broker_url = current_app.config.get("CELERY_BROKER_URL") or ""

    if not broker_url or broker_url == "memory://":
        return {
            "status": "unknown",
            "message": "Celery broker is in-process; workers are not reachable.",
            "workers": [],
        }

    try:
        from celery import Celery
        inspector_client = Celery(broker=broker_url)
        reply = inspector_client.control.inspect(timeout=1.0).ping()
    except Exception:
        current_app.logger.exception("health: celery broker check failed")
        return {
            "status": "broker_error",
            "message": "Celery broker is unreachable.",
            "workers": [],
        }

    if not reply:
        return {
            "status": "no_workers",
            "message": "No Celery workers responded.",
            "workers": [],
        }

    worker_names = sorted(reply.keys())
    return {
        "status": "ok",
        "message": f"{len(worker_names)} worker(s) responded.",
        "workers": worker_names,
    }


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


# ── Users management ──────────────────────────────────────
@bp.get("/users")
@login_required
@requires(Perm.ADMIN_VIEW)
def users_list():
    """Paginated, searchable user list."""
    q = (request.args.get("q") or "").strip()
    role_filter = (request.args.get("role") or "").strip()
    status_filter = (request.args.get("status") or "").strip()
    page = _parse_page(request.args.get("page"))

    query = User.query.filter(User.deleted_at.is_(None))

    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                User.email.ilike(like),
                User.display_name.ilike(like),
                User.phone.ilike(like),
            )
        )
    if role_filter in ("student", "moderator", "campus_admin", "platform_admin"):
        query = query.filter(User.role == role_filter)
    if status_filter in ("active", "suspended", "blocked"):
        query = query.filter(User.status == status_filter)

    pagination = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=USERS_PER_PAGE, error_out=False
    )

    return render_template(
        "pages/admin/users_list.html",
        users=pagination.items,
        pagination=pagination,
        q=q,
        role_filter=role_filter,
        status_filter=status_filter,
    )


@bp.get("/users/<user_id>")
@login_required
@requires(Perm.ADMIN_VIEW)
def user_detail(user_id):
    """Single user detail view."""
    u = db.session.get(User, user_id)
    if not u or u.deleted_at is not None:
        abort(404)

    push_sub_count = PushSubscription.query.filter_by(user_id=u.id).count()
    notif_count = Notification.query.filter_by(recipient_id=u.id).count()
    report_count = CampusReport.query.filter_by(reported_by=u.id).count()

    return render_template(
        "pages/admin/user_detail.html",
        u=u,
        push_sub_count=push_sub_count,
        notif_count=notif_count,
        report_count=report_count,
    )


@bp.post("/users/<user_id>/suspend")
@login_required
@requires(Perm.ADMIN_MANAGE_USERS)
def suspend_user(user_id):
    u = db.session.get(User, user_id)
    if not u or u.deleted_at is not None:
        abort(404)
    if u.id == current_user.id:
        flash("You can't suspend your own account.", "error")
        return redirect(url_for("admin.user_detail", user_id=u.id))
    if u.status == "suspended":
        flash("Account is already suspended.", "info")
        return redirect(url_for("admin.user_detail", user_id=u.id))

    before = {"status": u.status}
    u.status = "suspended"
    audit_log.log(
        current_user.id, "user.suspend", "user", u.id,
        before=before, after={"status": "suspended"},
    )
    db.session.commit()
    flash(f"Suspended {u.email}.", "success")
    return redirect(url_for("admin.user_detail", user_id=u.id))


@bp.post("/users/<user_id>/restore")
@login_required
@requires(Perm.ADMIN_MANAGE_USERS)
def restore_user(user_id):
    u = db.session.get(User, user_id)
    if not u or u.deleted_at is not None:
        abort(404)
    if u.status == "active":
        flash("Account is already active.", "info")
        return redirect(url_for("admin.user_detail", user_id=u.id))

    before = {"status": u.status}
    u.status = "active"
    audit_log.log(
        current_user.id, "user.restore", "user", u.id,
        before=before, after={"status": "active"},
    )
    db.session.commit()
    flash(f"Restored {u.email}.", "success")
    return redirect(url_for("admin.user_detail", user_id=u.id))


@bp.get("/universities")
@login_required
@requires(Perm.ADMIN_VIEW)
def universities_list():
    return _placeholder(
        "Universities & Campuses",
        section_icon="universities",
        teaser=(
            "Add, edit, activate and deactivate universities and their "
            "campuses, and manage the faculty and department structure "
            "beneath each campus."
        ),
    )


# ── Campus Locations (read-only) ──────────────────────────
@bp.get("/locations")
@login_required
@requires(Perm.ADMIN_VIEW)
def locations_list():
    """Paginated, filterable list of campus map locations.

    Read-only. Editing is deferred to a later phase. All filters are
    backed by real columns; no metric is fabricated.
    """
    status_filter = (request.args.get("status") or "").strip()
    category_filter = (request.args.get("category") or "").strip()
    campus_filter = (request.args.get("campus") or "").strip()
    source_filter = (request.args.get("source") or "").strip()
    q = (request.args.get("q") or "").strip()
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()
    page = _parse_page(request.args.get("page"))

    # Distinct values from the DB for status/source/campus; from the
    # canonical registry for categories.
    status_choices = [
        row[0] for row in db.session.execute(
            select(Location.status).distinct().order_by(Location.status)
        ).all()
    ]
    source_choices = [
        row[0] for row in db.session.execute(
            select(Location.source).distinct().order_by(Location.source)
        ).all()
    ]
    category_choices = loc_cats.all_categories()

    campus_id_rows = db.session.execute(
        select(Location.campus_id).distinct()
    ).all()
    campus_id_set = {row[0] for row in campus_id_rows if row[0]}
    campus_choices = []
    if campus_id_set:
        campus_choices = (
            Campus.query
            .filter(Campus.id.in_(campus_id_set))
            .order_by(Campus.name)
            .all()
        )

    # Pagination is done via Query.paginate() on a plain Location query,
    # so Flask-SQLAlchemy's own count runs against a single-entity select
    # and cannot produce a cartesian product. Coordinates are then fetched
    # for just this page's rows in a second, bounded query.
    query = Location.query

    if status_filter and status_filter in status_choices:
        query = query.filter(Location.status == status_filter)
    if category_filter and loc_cats.is_valid(category_filter):
        query = query.filter(Location.category == category_filter)
    if campus_filter and campus_filter in campus_id_set:
        query = query.filter(Location.campus_id == campus_filter)
    if source_filter and source_filter in source_choices:
        query = query.filter(Location.source == source_filter)
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Location.name.ilike(like),
                Location.description.ilike(like),
            )
        )

    date_from_dt = _parse_iso_date(date_from)
    date_to_dt = _parse_iso_date(date_to)
    if date_to_dt is not None:
        # Inclusive of the whole end day.
        date_to_dt = date_to_dt + timedelta(days=1)
    if date_from_dt is not None:
        query = query.filter(Location.created_at >= date_from_dt)
    if date_to_dt is not None:
        query = query.filter(Location.created_at < date_to_dt)

    pagination = query.order_by(Location.name).paginate(
        page=page, per_page=LOCATIONS_PER_PAGE, error_out=False
    )
    locations = pagination.items

    # Fetch coordinates for just this page's items in one query.
    # Extracting lat/lng via ST_Y/ST_X on the point column is a
    # per-row function evaluation; batching by id keeps it one
    # round-trip regardless of page size.
    coords_by_id = {}
    if locations:
        location_ids = [loc.id for loc in locations]
        coord_rows = db.session.execute(
            select(
                Location.id,
                func.ST_Y(Location.point),
                func.ST_X(Location.point),
            ).where(Location.id.in_(location_ids))
        ).all()
        for row in coord_rows:
            coords_by_id[row[0]] = {
                "lat": float(row[1]) if row[1] is not None else None,
                "lng": float(row[2]) if row[2] is not None else None,
            }

    lookups = _bulk_resolve_locations(locations)

    return render_template(
        "pages/admin/locations_list.html",
        pagination=pagination,
        locations=locations,
        coords_by_id=coords_by_id,
        lookups=lookups,
        status_choices=status_choices,
        category_choices=category_choices,
        campus_choices=campus_choices,
        source_choices=source_choices,
        status_filter=status_filter,
        category_filter=category_filter,
        campus_filter=campus_filter,
        source_filter=source_filter,
        q=q,
        date_from=date_from,
        date_to=date_to,
    )


@bp.get("/locations/<location_id>")
@login_required
@requires(Perm.ADMIN_VIEW)
def location_detail(location_id):
    """Single Location detail, read-only."""
    loc = db.session.get(Location, location_id)
    if loc is None:
        abort(404)

    # Extract coordinates in the same query as the row fetch.
    coord_row = db.session.execute(
        select(
            func.ST_Y(Location.point),
            func.ST_X(Location.point),
        ).where(Location.id == loc.id)
    ).first()
    if coord_row is not None:
        lat = float(coord_row[0]) if coord_row[0] is not None else None
        lng = float(coord_row[1]) if coord_row[1] is not None else None
    else:
        lat = lng = None

    campus = db.session.get(Campus, loc.campus_id) if loc.campus_id else None
    creator = db.session.get(User, loc.created_by) if loc.created_by else None
    verifier = db.session.get(User, loc.verified_by) if loc.verified_by else None

    # Reverse-lookup: the suggestion that produced this location, if any.
    # The FK lives on the suggestion side, so this is a small indexed query.
    originating_suggestion = (
        LocationSuggestion.query
        .filter_by(approved_location_id=loc.id)
        .first()
    )

    return render_template(
        "pages/admin/location_detail.html",
        loc=loc,
        lat=lat,
        lng=lng,
        campus=campus,
        creator=creator,
        verifier=verifier,
        category_label=_category_label(loc.category),
        status_pill=_location_status_pill(loc.status),
        source_label=_location_source_label(loc.source),
        originating_suggestion=originating_suggestion,
    )


# ── Campus Pulse moderation ───────────────────────────────
@bp.get("/pulse")
@login_required
@requires(Perm.ADMIN_VIEW)
def pulse_list():
    """Paginated, filterable list of Campus Pulse reports."""
    status_filter = (request.args.get("status") or "").strip()
    moderation_filter = (request.args.get("moderation") or "").strip()
    category_filter = (request.args.get("category") or "").strip()
    campus_filter = (request.args.get("campus") or "").strip()
    reporter_email = (request.args.get("reporter") or "").strip()
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()
    flagged_only = (request.args.get("flagged") or "").strip() == "1"
    page = _parse_page(request.args.get("page"))

    # Distinct values come from the DB for status/moderation,
    # and from the canonical Python registry for categories.
    status_choices = [
        row[0] for row in db.session.execute(
            select(CampusReport.status).distinct().order_by(CampusReport.status)
        ).all()
    ]
    moderation_choices = [
        row[0] for row in db.session.execute(
            select(CampusReport.moderation_status).distinct()
            .order_by(CampusReport.moderation_status)
        ).all()
    ]
    category_choices = pulse_categories.groups()

    campus_id_rows = db.session.execute(
        select(CampusReport.campus_id).distinct()
    ).all()
    campus_id_set = {row[0] for row in campus_id_rows if row[0]}
    campus_choices = []
    if campus_id_set:
        campus_choices = (
            Campus.query
            .filter(Campus.id.in_(campus_id_set))
            .order_by(Campus.name)
            .all()
        )

    query = CampusReport.query

    if status_filter and status_filter in status_choices:
        query = query.filter(CampusReport.status == status_filter)

    if moderation_filter and moderation_filter in moderation_choices:
        query = query.filter(CampusReport.moderation_status == moderation_filter)

    if category_filter and pulse_categories.is_valid(category_filter):
        query = query.filter(CampusReport.category == category_filter)

    if campus_filter and campus_filter in campus_id_set:
        query = query.filter(CampusReport.campus_id == campus_filter)

    if reporter_email:
        normalized = reporter_email.lower()
        reporter = User.query.filter(
            func.lower(User.email) == normalized
        ).first()
        if reporter is None:
            # Force zero results without breaking the template.
            query = query.filter(CampusReport.id == "__no_such_reporter__")
        else:
            query = query.filter(CampusReport.reported_by == reporter.id)

    if flagged_only:
        query = query.filter(CampusReport.flag_count > 0)

    date_from_dt = _parse_iso_date(date_from)
    date_to_dt = _parse_iso_date(date_to)
    if date_to_dt is not None:
        # Inclusive of the whole end day.
        date_to_dt = date_to_dt + timedelta(days=1)

    if date_from_dt is not None:
        query = query.filter(CampusReport.reported_at >= date_from_dt)
    if date_to_dt is not None:
        query = query.filter(CampusReport.reported_at < date_to_dt)

    pagination = query.order_by(CampusReport.reported_at.desc()).paginate(
        page=page, per_page=PULSE_PER_PAGE, error_out=False
    )

    lookups = _bulk_resolve_pulse(pagination.items)

    return render_template(
        "pages/admin/pulse_list.html",
        pagination=pagination,
        reports=pagination.items,
        lookups=lookups,
        status_choices=status_choices,
        moderation_choices=moderation_choices,
        category_choices=category_choices,
        campus_choices=campus_choices,
        status_filter=status_filter,
        moderation_filter=moderation_filter,
        category_filter=category_filter,
        campus_filter=campus_filter,
        reporter_email=reporter_email,
        date_from=date_from,
        date_to=date_to,
        flagged_only=flagged_only,
    )


@bp.get("/pulse/<report_id>")
@login_required
@requires(Perm.ADMIN_VIEW)
def pulse_detail(report_id):
    """Single Pulse report, with moderation history and actions."""
    report = db.session.get(CampusReport, report_id)
    if report is None:
        abort(404)

    reporter = None
    if report.reported_by:
        reporter = db.session.get(User, report.reported_by)

    campus = None
    if report.campus_id:
        campus = db.session.get(Campus, report.campus_id)

    location = None
    if report.location_id:
        location = db.session.get(Location, report.location_id)

    confirmations = (
        ReportConfirmation.query
        .filter_by(report_id=report.id)
        .order_by(ReportConfirmation.created_at.desc())
        .all()
    )
    flags = (
        ReportFlag.query
        .filter_by(report_id=report.id)
        .order_by(ReportFlag.created_at.desc())
        .all()
    )

    history_user_ids = set()
    for c in confirmations:
        if c.user_id:
            history_user_ids.add(c.user_id)
    for f in flags:
        if f.user_id:
            history_user_ids.add(f.user_id)
    history_users = {}
    if history_user_ids:
        history_users = {
            u.id: u for u in User.query.filter(User.id.in_(history_user_ids)).all()
        }

    return render_template(
    "pages/admin/pulse_detail.html",
    report=report,
    reporter=reporter,
    campus=campus,
    location=location,
    confirmations=confirmations,
    flags=flags,
    history_users=history_users,
    category_label=_pulse_category_label(report.category),
    status_pill=_pulse_status_pill(report.status),
    moderation_pill=_moderation_pill(report.moderation_status),
    now=datetime.now(timezone.utc),
    )


def _pulse_moderate(report_id: str, action: str, *, flash_ok: str):
    """Shared body for hide / remove / restore.

    Fetches the report, applies the moderation change through the
    existing pulse_moderation functions, writes one audit row, and
    commits. Rolls back on any exception. Returns a redirect back to
    the admin Pulse detail page in all cases.

    Guarantees:
      - 404 for unknown report ids.
      - No audit row when the requested action would not change state.
      - `status` and `moderation_status` remain consistent: hiding a
        removed report is rejected (it would leave the report in a
        mixed state), and removing an already-removed report is a no-op.
    """
    report = db.session.get(CampusReport, report_id)
    if report is None:
        abort(404)

    before = {
        "moderation_status": report.moderation_status,
        "status": report.status,
    }

    # ── Guard against no-op / inconsistent transitions ────
    if action == "hide":
        if report.moderation_status == "hidden":
            flash("Report is already hidden.", "info")
            return redirect(url_for("admin.pulse_detail", report_id=report.id))
        if report.moderation_status == "removed" or report.status == "removed":
            flash("Can't hide a removed report. Restore it first.", "error")
            return redirect(url_for("admin.pulse_detail", report_id=report.id))
        pulse_moderation.hide(report)

    elif action == "remove":
        if report.moderation_status == "removed" and report.status == "removed":
            flash("Report is already removed.", "info")
            return redirect(url_for("admin.pulse_detail", report_id=report.id))
        pulse_moderation.remove(report)

    elif action == "restore":
        if report.moderation_status == "visible" and report.status != "removed":
            flash("Report is already visible.", "info")
            return redirect(url_for("admin.pulse_detail", report_id=report.id))
        pulse_moderation.restore(report)

    else:
        # Defensive: unknown action. Should never happen — the routes
        # below only pass known strings.
        abort(404)

    after = {
        "moderation_status": report.moderation_status,
        "status": report.status,
    }

    try:
        audit_log.log(
            current_user.id,
            f"pulse.{action}",
            "campus_report",
            report.id,
            before=before,
            after=after,
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("admin pulse: moderation commit failed")
        flash("Something went wrong. The change was not saved.", "error")
        return redirect(url_for("admin.pulse_detail", report_id=report.id))

    flash(flash_ok, "success")
    return redirect(url_for("admin.pulse_detail", report_id=report.id))


@bp.post("/pulse/<report_id>/hide")
@login_required
@requires(Perm.ADMIN_VIEW)
def pulse_hide(report_id):
    return _pulse_moderate(
        report_id, "hide",
        flash_ok="Report hidden.",
    )


@bp.post("/pulse/<report_id>/remove")
@login_required
@requires(Perm.ADMIN_VIEW)
def pulse_remove(report_id):
    return _pulse_moderate(
        report_id, "remove",
        flash_ok="Report removed.",
    )


@bp.post("/pulse/<report_id>/restore")
@login_required
@requires(Perm.ADMIN_VIEW)
def pulse_restore(report_id):
    return _pulse_moderate(
        report_id, "restore",
        flash_ok="Report restored.",
    )


# ── Location suggestions moderation ───────────────────────
@bp.get("/suggestions")
@login_required
@requires(Perm.ADMIN_VIEW)
def suggestions_list():
    """Paginated, filterable list of location suggestions."""
    status_filter = (request.args.get("status") or "").strip()
    category_filter = (request.args.get("category") or "").strip()
    campus_filter = (request.args.get("campus") or "").strip()
    submitter_email = (request.args.get("submitter") or "").strip()
    q = (request.args.get("q") or "").strip()
    page = _parse_page(request.args.get("page"))

    status_choices = [
        row[0] for row in db.session.execute(
            select(LocationSuggestion.status).distinct().order_by(LocationSuggestion.status)
        ).all()
    ]

    category_choices = loc_cats.all_categories()

    campus_id_rows = db.session.execute(
        select(LocationSuggestion.campus_id).distinct()
    ).all()
    campus_id_set = {row[0] for row in campus_id_rows if row[0]}
    campus_choices = []
    if campus_id_set:
        campus_choices = (
            Campus.query
            .filter(Campus.id.in_(campus_id_set))
            .order_by(Campus.name)
            .all()
        )

    query = LocationSuggestion.query

    if status_filter and status_filter in status_choices:
        query = query.filter(LocationSuggestion.status == status_filter)

    if category_filter and loc_cats.is_valid(category_filter):
        query = query.filter(LocationSuggestion.category == category_filter)

    if campus_filter and campus_filter in campus_id_set:
        query = query.filter(LocationSuggestion.campus_id == campus_filter)

    if submitter_email:
        normalized = submitter_email.lower()
        submitter = User.query.filter(
            func.lower(User.email) == normalized
        ).first()
        if submitter is None:
            query = query.filter(LocationSuggestion.id == "__no_such_submitter__")
        else:
            query = query.filter(LocationSuggestion.proposed_by == submitter.id)

    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                LocationSuggestion.name.ilike(like),
                LocationSuggestion.description.ilike(like),
            )
        )

    pagination = query.order_by(LocationSuggestion.created_at.desc()).paginate(
        page=page, per_page=SUGGESTIONS_PER_PAGE, error_out=False
    )

    lookups = _bulk_resolve(pagination.items)

    return render_template(
        "pages/admin/suggestions_list.html",
        pagination=pagination,
        suggestions=pagination.items,
        lookups=lookups,
        status_choices=status_choices,
        category_choices=category_choices,
        campus_choices=campus_choices,
        status_filter=status_filter,
        category_filter=category_filter,
        campus_filter=campus_filter,
        submitter_email=submitter_email,
        q=q,
    )


@bp.get("/suggestions/<sug_id>")
@login_required
@requires(Perm.ADMIN_VIEW)
def suggestion_detail(sug_id):
    """Single suggestion detail, with moderation state."""
    sug = db.session.get(LocationSuggestion, sug_id)
    if sug is None:
        abort(404)

    campus = None
    if sug.campus_id:
        campus = db.session.get(Campus, sug.campus_id)

    proposer = None
    if sug.proposed_by:
        proposer = db.session.get(User, sug.proposed_by)

    moderator = None
    if sug.moderated_by:
        moderator = db.session.get(User, sug.moderated_by)

    approved_location = None
    if sug.approved_location_id:
        approved_location = db.session.get(Location, sug.approved_location_id)

    return render_template(
        "pages/admin/suggestion_detail.html",
        sug=sug,
        campus=campus,
        proposer=proposer,
        moderator=moderator,
        approved_location=approved_location,
        category_label=_category_label(sug.category),
        status_pill=_status_pill(sug.status),
    )


# ── Notifications & Push (read-only overview) ─────────────
@bp.get("/notifications")
@login_required
@requires(Perm.ADMIN_VIEW)
def notifications_overview():
    """Read-only dashboard of Notification and PushSubscription state.

    Every count shown here is backed by a real column. No metric is
    fabricated. Specifically, this page does not show push failure
    counts or delivery rates — those are not persisted anywhere in the
    current schema.
    """
    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)
    cutoff_7d = now - timedelta(days=ACTIVE_PUSH_DAYS)
    cutoff_30d = now - timedelta(days=STALE_PUSH_DAYS)

    # ── Notification counts ─────────────────────────────
    total_notifications, total_notif_err = _safe(
        lambda: db.session.execute(
            select(func.count(Notification.id))
        ).scalar_one()
    )
    unread_notifications, unread_notif_err = _safe(
        lambda: db.session.execute(
            select(func.count(Notification.id))
            .where(Notification.read_at.is_(None))
            .where(Notification.dismissed_at.is_(None))
        ).scalar_one()
    )
    notifications_24h, notif_24h_err = _safe(
        lambda: db.session.execute(
            select(func.count(Notification.id))
            .where(Notification.created_at >= cutoff_24h)
        ).scalar_one()
    )

    # ── Subscription counts ─────────────────────────────
    total_subscriptions, total_sub_err = _safe(
        lambda: db.session.execute(
            select(func.count(PushSubscription.id))
        ).scalar_one()
    )
    active_subscriptions, active_sub_err = _safe(
        lambda: db.session.execute(
            select(func.count(PushSubscription.id))
            .where(PushSubscription.last_success_at.isnot(None))
            .where(PushSubscription.last_success_at >= cutoff_7d)
        ).scalar_one()
    )
    stale_subscriptions, stale_sub_err = _safe(
        lambda: db.session.execute(
            select(func.count(PushSubscription.id))
            .where(PushSubscription.created_at < cutoff_30d)
            .where(PushSubscription.last_success_at.is_(None))
        ).scalar_one()
    )

    # ── By type ─────────────────────────────────────────
    # One row per type in the canonical registry, plus any types that
    # actually exist in the database (in case the registry was updated
    # after rows were written). Fixed order: registry first, then any
    # additional keys alphabetically. Counts come from a single grouped
    # query; missing keys render as zero.
    from app.notifications import types as ntypes

    def _type_counts():
        rows = db.session.execute(
            select(
                Notification.type,
                func.count(Notification.id),
                func.count(Notification.id).filter(Notification.read_at.is_(None)),
            )
            .group_by(Notification.type)
        ).all()
        return rows

    type_rows, type_err = _safe(_type_counts, default=[])

    # Build a dict keyed by type string → (total, unread)
    counts_by_type = {}
    for t, total, unread in type_rows:
        counts_by_type[t] = {"total": total, "unread": unread}

    # Ordered list: every registered key first, preserving insertion
    # order from REGISTRY; then any unregistered keys seen in the DB.
    ordered_keys = list(ntypes.REGISTRY.keys())
    for t in sorted(counts_by_type.keys()):
        if t not in ordered_keys:
            ordered_keys.append(t)

    type_breakdown = [
        {
            "key": t,
            "label": _notification_type_label(t),
            "category": _notification_type_category(t),
            "total": counts_by_type.get(t, {}).get("total", 0),
            "unread": counts_by_type.get(t, {}).get("unread", 0),
        }
        for t in ordered_keys
    ]

    # ── Recent notifications ────────────────────────────
    def _recent_notifications():
        return (
            Notification.query
            .order_by(Notification.created_at.desc())
            .limit(10)
            .all()
        )

    recent_notifications, recent_notif_err = _safe(
        _recent_notifications, default=[]
    )
    recent_notif_lookups = _bulk_resolve_recipients(recent_notifications)

    # ── Recent subscriptions ────────────────────────────
    def _recent_subscriptions():
        return (
            PushSubscription.query
            .order_by(PushSubscription.created_at.desc())
            .limit(10)
            .all()
        )

    recent_subscriptions, recent_sub_err = _safe(
        _recent_subscriptions, default=[]
    )
    recent_sub_lookups = _bulk_resolve_subscription_users(recent_subscriptions)

    return render_template(
        "pages/admin/notifications.html",
        total_notifications=total_notifications,
        total_notifications_err=total_notif_err,
        unread_notifications=unread_notifications,
        unread_notifications_err=unread_notif_err,
        notifications_24h=notifications_24h,
        notifications_24h_err=notif_24h_err,
        total_subscriptions=total_subscriptions,
        total_subscriptions_err=total_sub_err,
        active_subscriptions=active_subscriptions,
        active_subscriptions_err=active_sub_err,
        stale_subscriptions=stale_subscriptions,
        stale_subscriptions_err=stale_sub_err,
        type_breakdown=type_breakdown,
        type_breakdown_err=type_err,
        recent_notifications=recent_notifications,
        recent_notifications_err=recent_notif_err,
        recent_notif_lookups=recent_notif_lookups,
        recent_subscriptions=recent_subscriptions,
        recent_subscriptions_err=recent_sub_err,
        recent_sub_lookups=recent_sub_lookups,
        shorten_ua=_shorten_ua,
    )


# ── Analytics stub ────────────────────────────────────────
@bp.get("/analytics")
@login_required
@requires(Perm.ADMIN_VIEW)
def analytics():
    return _placeholder(
        "Analytics",
        section_icon="analytics",
        teaser=(
            "Trends across users, reports, locations, and notification "
            "engagement — filterable by university, campus and date range."
        ),
    )


# ── Audit logs ────────────────────────────────────────────
@bp.get("/audit")
@login_required
@requires(Perm.ADMIN_VIEW)
def audit_list():
    """Paginated, filterable audit log list."""
    action_filter = (request.args.get("action") or "").strip()
    entity_filter = (request.args.get("entity") or "").strip()
    actor_email = (request.args.get("actor") or "").strip()
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()
    page = _parse_page(request.args.get("page"))

    action_choices = [
        row[0] for row in db.session.execute(
            select(AuditLog.action).distinct().order_by(AuditLog.action)
        ).all()
    ]
    entity_choices = [
        row[0] for row in db.session.execute(
            select(AuditLog.entity_type).distinct().order_by(AuditLog.entity_type)
        ).all()
    ]

    actor_id_filter = None
    actor_lookup_failed = False
    if actor_email:
        normalized = actor_email.lower()
        actor = User.query.filter(
            func.lower(User.email) == normalized
        ).first()
        if actor is None:
            actor_lookup_failed = True
            actor_id_filter = "__no_such_actor__"
        else:
            actor_id_filter = actor.id

    date_from_dt = _parse_iso_date(date_from)
    date_to_dt = _parse_iso_date(date_to)
    if date_to_dt is not None:
        date_to_dt = date_to_dt + timedelta(days=1)

    query = AuditLog.query

    if action_filter and action_filter in action_choices:
        query = query.filter(AuditLog.action == action_filter)
    if entity_filter and entity_filter in entity_choices:
        query = query.filter(AuditLog.entity_type == entity_filter)
    if actor_id_filter is not None:
        query = query.filter(AuditLog.actor_id == actor_id_filter)
    if date_from_dt is not None:
        query = query.filter(AuditLog.created_at >= date_from_dt)
    if date_to_dt is not None:
        query = query.filter(AuditLog.created_at < date_to_dt)

    pagination = query.order_by(AuditLog.created_at.desc()).paginate(
        page=page, per_page=AUDIT_PER_PAGE, error_out=False
    )

    rows = []
    for entry in pagination.items:
        rows.append({
            "entry": entry,
            "action_label": _action_label(entry.action),
            "summary": _audit_summary(entry),
        })

    return render_template(
        "pages/admin/audit_list.html",
        rows=rows,
        pagination=pagination,
        action_choices=action_choices,
        entity_choices=entity_choices,
        action_filter=action_filter,
        entity_filter=entity_filter,
        actor_email=actor_email,
        date_from=date_from,
        date_to=date_to,
        actor_lookup_failed=actor_lookup_failed,
    )


@bp.get("/audit/<log_id>")
@login_required
@requires(Perm.ADMIN_VIEW)
def audit_detail(log_id):
    """Single audit log entry."""
    entry = db.session.get(AuditLog, log_id)
    if entry is None:
        abort(404)

    actor = None
    if entry.actor_id:
        actor = db.session.get(User, entry.actor_id)

    entity_url = None
    if entry.entity_type == "user" and entry.entity_id:
        target = db.session.get(User, entry.entity_id)
        if target is not None and target.deleted_at is None:
            entity_url = url_for("admin.user_detail", user_id=target.id)

    return render_template(
        "pages/admin/audit_detail.html",
        entry=entry,
        action_label=_action_label(entry.action),
        actor=actor,
        entity_url=entity_url,
    )


# ── System health stub ────────────────────────────────────
@bp.get("/health")
@login_required
@requires(Perm.ADMIN_VIEW)
def health():
    """Read-only operational status for the platform.

    Each dependency check is isolated: a failure in one produces a
    red/amber status on the page, never a 500. Audit queries are
    wrapped in _safe() so a slow or failed audit read degrades to
    'unavailable' rather than blanking the page.
    """
    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)

    checks = {
        # The application process itself is the thing answering this
        # request. If this route is executing, the app is up.
        "application": {"status": "ok", "message": "Serving requests."},
        "database": _check_db(),
        "redis": _check_redis(),
        "celery": _check_celery(),
    }

    def _recent_audit_health():
        return (
            AuditLog.query
            .order_by(AuditLog.created_at.desc())
            .limit(10)
            .all()
        )

    def _audit_count_24h():
        return db.session.execute(
            select(func.count(AuditLog.id))
            .where(AuditLog.created_at >= cutoff_24h)
        ).scalar_one()

    recent_audit, recent_audit_err = _safe(_recent_audit_health, default=[])
    audit_count_24h, audit_count_24h_err = _safe(_audit_count_24h)

    return render_template(
        "pages/admin/health.html",
        checks=checks,
        checked_at=now,
        recent_audit=recent_audit,
        recent_audit_err=recent_audit_err,
        audit_count_24h=audit_count_24h,
        audit_count_24h_err=audit_count_24h_err,
    )