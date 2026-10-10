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
from sqlalchemy import func, select

from app.core import audit as audit_log
from app.core.permissions import requires, Perm
from app.extensions import db
from app.models import User, University, Campus
from app.models.audit import AuditLog
from app.maps import categories as loc_cats
from app.maps.models import Location, LocationSuggestion
from app.notifications.models import Notification, PushSubscription
from app.pulse.models import CampusReport


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
    page = max(1, int(request.args.get("page") or 1))

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


@bp.get("/locations")
@login_required
@requires(Perm.ADMIN_VIEW)
def locations_list():
    return _placeholder(
        "Campus Locations",
        section_icon="locations",
        teaser=(
            "Review, edit and moderate the campus map locations students "
            "see — including categories, coordinates, and approval status."
        ),
    )


@bp.get("/pulse")
@login_required
@requires(Perm.ADMIN_VIEW)
def pulse_list():
    return _placeholder(
        "Campus Pulse",
        section_icon="pulse",
        teaser=(
            "Moderate and review Campus Pulse reports — investigate flagged "
            "posts, review reports by campus and category, and manage the "
            "moderation queue."
        ),
    )


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

    # Distinct status values present in the table; matches the audit
    # pattern so we don't hardcode an enum that could drift.
    status_choices = [
        row[0] for row in db.session.execute(
            select(LocationSuggestion.status).distinct().order_by(LocationSuggestion.status)
        ).all()
    ]

    # Categories come from the canonical Python registry, not from
    # the DB, because the DB is not enforcing the vocabulary.
    category_choices = loc_cats.all_categories()

    # Campus choices: only campuses that actually have suggestions.
    # Avoids offering an option that yields an empty page.
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
            # Force zero results without breaking the template.
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

    # Resolve related entities individually — one suggestion, no N+1
    # concern here.
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


@bp.get("/notifications")
@login_required
@requires(Perm.ADMIN_VIEW)
def notifications_overview():
    return _placeholder(
        "Notifications & Push",
        section_icon="notifications",
        teaser=(
            "Compose and target notifications, monitor delivery, and review "
            "push subscription health across iOS and web clients."
        ),
    )


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

    # Distinct values for the filter dropdowns. Cheap on a small
    # table (action is indexed; entity_type is not, but cardinality
    # is very low). Empty list when the table is empty.
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

    # Resolve the actor filter (email -> user id) with a normalized
    # exact match — email is an identifier, not a free-text search,
    # so a partial match would be ambiguous. A non-matching email
    # yields an empty result set; the filter is still surfaced back
    # to the template so the admin sees what they typed.
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

    def _parse_date(value: str):
        """Parse YYYY-MM-DD from an <input type="date">; None on failure."""
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            return None

    date_from_dt = _parse_date(date_from)
    date_to_dt = _parse_date(date_to)
    if date_to_dt is not None:
        # Make the upper bound inclusive of the whole end day.
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

    # Attach a rendered summary to each row so the template stays
    # dumb. Done in Python rather than a template filter because the
    # logic touches two JSON columns.
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

    # Resolve the actor if the account still exists. Soft-deleted
    # actors are still returned by db.session.get; the template
    # decides whether to render a link.
    actor = None
    if entry.actor_id:
        actor = db.session.get(User, entry.actor_id)

    # When the entity is a user, offer a link to that user's detail
    # page — but only when the target still exists and is not
    # soft-deleted, otherwise the target route would 404.
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


@bp.get("/health")
@login_required
@requires(Perm.ADMIN_VIEW)
def health():
    return _placeholder(
        "System Health",
        section_icon="health",
        teaser=(
            "Live status for the database, Redis, push delivery, background "
            "workers, and the API — plus recent incidents."
        ),
    )