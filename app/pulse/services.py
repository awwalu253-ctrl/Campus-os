from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import selectinload

from sqlalchemy import select

from app.extensions import db
from app.models import User
from app.models.user import StudentProfile
from app.notifications import services as notifications
from app.notifications import types as ntypes
from app.pulse import categories
from app.pulse.models import CampusReport, ReportConfirmation, ReportFlag
from app.users import trust as trust_engine


# ── Confidence derivation ─────────────────────────────────
def compute_confidence(report: CampusReport) -> str:
    """
    Confidence is derived, never user-set.

    Heuristic:
      - Base on confirmation_count minus disagreement_count
      - Weight slightly by age (older reports less confident unless
        recently re-confirmed — simplified here)
      - Penalize by flag_count

    Returns 'low' | 'medium' | 'high'.
    """
    score = report.confirmation_count - report.disagreement_count
    score -= report.flag_count * 2

    if score >= 5:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


# ── Create ────────────────────────────────────────────────
def create_report(*, user: User, campus_id: str, category: str,
                  description: str | None = None,
                  location_id: str | None = None,
                  image_key: str | None = None) -> CampusReport:
    if not categories.is_valid(category):
        raise ValueError(f"Unknown category: {category}")

    cat_meta = categories.get(category)
    ttl = timedelta(minutes=cat_meta["default_ttl_min"])

    report = CampusReport(
        campus_id=campus_id,
        location_id=location_id,
        category=category,
        description=(description or "").strip()[:500] or None,
        image_key=image_key,
        reported_by=user.id,
        expires_at=datetime.now(timezone.utc) + ttl,
        status="active",
    )
    db.session.add(report)
    db.session.flush()
    trust_engine.on_report_created(user)

    if ntypes.is_campus_notifiable(category):
        _notify_campus_of_report(report, reporter_id=user.id)

    return report


def _notify_campus_of_report(report: CampusReport, *, reporter_id: str) -> int:
    """Fan out a campus-wide notification for a report.

    Recipient selection happens in the database: active, non-deleted
    users whose StudentProfile.campus_id matches the report's campus,
    excluding the reporter. One notification row per recipient.

    Dedupe key is (recipient_id, f"campus-report:{report.id}"). The
    partial unique index uq_notifications_recipient_dedupe guarantees
    at most one row per recipient for this report even if the caller
    retries.

    Runs inside the caller's transaction. Does NOT commit.

    Returns the number of notifications actually inserted (0 if all
    were deduped).
    """
    cat_meta = categories.get(report.category) or {}
    cat_label = cat_meta.get("label") or report.category.replace("_", " ")
    group = cat_meta.get("group", "Campus")

    title = f"New {group.lower()} report on campus"
    body = f'A new {group.lower()} report was posted: "{cat_label}".'
    if report.description:
        snippet = report.description.strip()[:100]
        if snippet:
            body = f'{body.rstrip(".")} — {snippet}'
    action_url = f"/pulse/report/{report.id}"

    # Recipients: active students on this campus, excluding the reporter.
    recipient_stmt = (
        select(StudentProfile.user_id)
        .join(User, User.id == StudentProfile.user_id)
        .where(StudentProfile.campus_id == report.campus_id)
        .where(User.status == "active")
        .where(User.deleted_at.is_(None))
        .where(StudentProfile.user_id != reporter_id)
    )
    recipient_ids = [row[0] for row in db.session.execute(recipient_stmt).all()]

    if not recipient_ids:
        return 0

    inserted = 0
    dedupe_key = f"campus-report:{report.id}"
    for recipient_id in recipient_ids:
        result = notifications.create_notification_if_new(
            recipient_id=recipient_id,
            type=ntypes.CAMPUS_SAFETY_REPORT,
            title=title,
            body=body,
            action_url=action_url,
            campus_id=report.campus_id,
            related_entity_type="campus_report",
            related_entity_id=report.id,
            dedupe_key=dedupe_key,
        )
        if result is not None:
            inserted += 1
    return inserted


# ── Confirm / disagree ────────────────────────────────────
def _existing_confirmation(report_id: str, user_id: str) -> ReportConfirmation | None:
    return ReportConfirmation.query.filter_by(
        report_id=report_id, user_id=user_id
    ).first()


def confirm_report(*, report: CampusReport, user: User) -> ReportConfirmation:
    if report.reported_by == user.id:
        raise ValueError("You can't confirm your own report.")
    if report.status != "active":
        raise ValueError("This report is no longer active.")

    existing = _existing_confirmation(report.id, user.id)
    if existing and existing.kind == "confirm":
        raise ValueError("You already confirmed this report.")

    if existing and existing.kind == "disagree":
        existing.kind = "confirm"
        report.disagreement_count = max(0, report.disagreement_count - 1)
        report.confirmation_count += 1
    else:
        db.session.add(ReportConfirmation(
            report_id=report.id, user_id=user.id, kind="confirm",
        ))
        report.confirmation_count += 1

    # Reporter gets credit
    reporter = db.session.get(User, report.reported_by) if report.reported_by else None
    if reporter:
        trust_engine.on_report_confirmed(reporter)

    # Confirmer gets a small credit
    trust_engine.on_confirmation_given(user, agreed_with_majority=True)

    report.confidence = compute_confidence(report)

    # Milestone notification — only at 1, 5, 10, 25, 50 confirmations.
    if (
        reporter
        and reporter.id != user.id
        and report.confirmation_count in ntypes.CONFIRMATION_MILESTONES
    ):
        cat_meta = categories.get(report.category) or {}
        cat_label = cat_meta.get("label", report.category.replace("_", " "))
        notifications.create_notification_if_new(
            recipient_id=reporter.id,
            type=ntypes.REPORT_CONFIRMATION_MILESTONE,
            title="Your report is gaining traction",
            body=(
                f"Your report about \"{cat_label}\" has been confirmed "
                f"{report.confirmation_count} "
                f"time{'s' if report.confirmation_count != 1 else ''}."
            ),
            action_url=f"/pulse/report/{report.id}",
            campus_id=report.campus_id,
            related_entity_type="campus_report",
            related_entity_id=report.id,
            dedupe_key=f"report-confirmation:{report.id}:{report.confirmation_count}",
        )

    return existing or report  # caller commits


def disagree_report(*, report: CampusReport, user: User) -> None:
    if report.reported_by == user.id:
        raise ValueError("You can't disagree with your own report.")
    if report.status != "active":
        raise ValueError("This report is no longer active.")

    existing = _existing_confirmation(report.id, user.id)
    if existing and existing.kind == "disagree":
        raise ValueError("You already disagreed with this report.")

    if existing and existing.kind == "confirm":
        existing.kind = "disagree"
        report.confirmation_count = max(0, report.confirmation_count - 1)
        report.disagreement_count += 1
    else:
        db.session.add(ReportConfirmation(
            report_id=report.id, user_id=user.id, kind="disagree",
        ))
        report.disagreement_count += 1

    reporter = db.session.get(User, report.reported_by) if report.reported_by else None
    if reporter:
        trust_engine.on_report_disagreed(reporter)

    trust_engine.on_confirmation_given(user, agreed_with_majority=False)
    report.confidence = compute_confidence(report)

    if reporter and reporter.id != user.id:
        cat_meta = categories.get(report.category) or {}
        cat_label = cat_meta.get("label", report.category.replace("_", " "))
        notifications.create_notification_if_new(
            recipient_id=reporter.id,
            type=ntypes.REPORT_DISAGREEMENT,
            title="Someone disagreed with your report",
            body=f"A student disagreed with your report about \"{cat_label}\".",
            action_url=f"/pulse/report/{report.id}",
            campus_id=report.campus_id,
            related_entity_type="campus_report",
            related_entity_id=report.id,
            dedupe_key=f"report-disagreement:{report.id}:{user.id}",
        )

    if reporter and reporter.id != user.id:
        cat_meta = categories.get(report.category) or {}
        cat_label = cat_meta.get("label", report.category.replace("_", " "))
        notifications.create_notification_if_new(
            recipient_id=reporter.id,
            type=ntypes.REPORT_DISAGREEMENT,
            title="Someone disagreed with your report",
            body=f"A student disagreed with your report about \"{cat_label}\".",
            action_url=f"/pulse/report/{report.id}",
            campus_id=report.campus_id,
            related_entity_type="campus_report",
            related_entity_id=report.id,
            dedupe_key=f"report-disagreement:{report.id}:{user.id}",
        )

    if reporter and reporter.id != user.id:
        cat_meta = categories.get(report.category) or {}
        cat_label = cat_meta.get("label", report.category.replace("_", " "))
        notifications.create_notification_if_new(
            recipient_id=reporter.id,
            type=ntypes.REPORT_DISAGREEMENT,
            title="Someone disagreed with your report",
            body=f"A student disagreed with your report about \"{cat_label}\".",
            action_url=f"/pulse/report/{report.id}",
            campus_id=report.campus_id,
            related_entity_type="campus_report",
            related_entity_id=report.id,
            dedupe_key=f"report-disagreement:{report.id}:{user.id}",
        )

    if reporter and reporter.id != user.id:
        cat_meta = categories.get(report.category) or {}
        cat_label = cat_meta.get("label", report.category.replace("_", " "))
        notifications.create_notification_if_new(
            recipient_id=reporter.id,
            type=ntypes.REPORT_DISAGREEMENT,
            title="Someone disagreed with your report",
            body=f"A student disagreed with your report about \"{cat_label}\".",
            action_url=f"/pulse/report/{report.id}",
            campus_id=report.campus_id,
            related_entity_type="campus_report",
            related_entity_id=report.id,
            dedupe_key=f"report-disagreement:{report.id}:{user.id}",
        )


# ── Flag ──────────────────────────────────────────────────
def flag_report(*, report: CampusReport, user: User, reason: str | None = None) -> None:
    existing = ReportFlag.query.filter_by(report_id=report.id, user_id=user.id).first()
    if existing:
        raise ValueError("You already flagged this report.")

    db.session.add(ReportFlag(report_id=report.id, user_id=user.id,
                              reason=(reason or "")[:120] or None))
    report.flag_count += 1

    reporter = db.session.get(User, report.reported_by) if report.reported_by else None
    if reporter:
        trust_engine.on_report_flagged(reporter)

    report.confidence = compute_confidence(report)

    if reporter and reporter.id != user.id:
        cat_meta = categories.get(report.category) or {}
        cat_label = cat_meta.get("label", report.category.replace("_", " "))
        notifications.create_notification_if_new(
            recipient_id=reporter.id,
            type=ntypes.REPORT_FLAGGED,
            title="Your report was flagged",
            body=(
                f"Someone flagged your report about \"{cat_label}\". "
                "A moderator will review it."
            ),
            action_url=f"/pulse/report/{report.id}",
            campus_id=report.campus_id,
            related_entity_type="campus_report",
            related_entity_id=report.id,
            dedupe_key=f"report-flag:{report.id}:{user.id}",
        )


# ── Queries ───────────────────────────────────────────────
def active_reports_for_campus(campus_id: str, *, limit: int = 30):
    now = datetime.now(timezone.utc)
    stmt = (
        select(CampusReport)
        .where(and_(
            CampusReport.campus_id == campus_id,
            CampusReport.status == "active",
            CampusReport.moderation_status == "visible",
            CampusReport.expires_at > now,
        ))
        .order_by(CampusReport.reported_at.desc())
        .limit(limit)
    )
    return db.session.execute(stmt).scalars().all()


def live_home_preview(campus_id: str, *, limit: int = 3):
    """3 most recent active reports for the home dashboard card."""
    return active_reports_for_campus(campus_id, limit=limit)


def get_report(report_id: str) -> CampusReport | None:
    return db.session.get(CampusReport, report_id)


# ── Expiry sweep (called by Celery) ───────────────────────
def sweep_expired() -> dict:
    """
    Mark expired reports as 'expired'. Recompute confidence on all active.
    Idempotent. Safe to run as often as desired.
    """
    now = datetime.now(timezone.utc)

    expired = (
        db.session.query(CampusReport)
        .filter(
            CampusReport.status == "active",
            CampusReport.expires_at <= now,
        )
        .all()
    )
    for r in expired:
        r.status = "expired"

        # Notify the reporter only if the report expired without any
        # confirmations. Reports that got confirmed are not "stale" —
        # they simply timed out, which is the normal lifecycle.
        if r.reported_by and r.confirmation_count == 0:
            cat_meta = categories.get(r.category) or {}
            cat_label = cat_meta.get("label", r.category.replace("_", " "))
            notifications.create_notification_if_new(
                recipient_id=r.reported_by,
                type=ntypes.REPORT_EXPIRED_STALE,
                title="Your report has gone stale",
                body=(
                    f"Your report about \"{cat_label}\" has expired "
                    "without receiving any confirmation."
                ),
                action_url=f"/pulse/report/{r.id}",
                campus_id=r.campus_id,
                related_entity_type="campus_report",
                related_entity_id=r.id,
                dedupe_key=f"report-expired-stale:{r.id}",
            )

    active = (
        db.session.query(CampusReport)
        .filter(CampusReport.status == "active")
        .all()
    )
    for r in active:
        new_conf = compute_confidence(r)
        if new_conf != r.confidence:
            r.confidence = new_conf

    db.session.commit()
    return {"expired": len(expired), "recomputed": len(active)}