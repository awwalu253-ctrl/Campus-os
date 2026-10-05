from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import User
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

    meta = categories.get(category)
    ttl = timedelta(minutes=meta["default_ttl_min"])

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
    return report


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