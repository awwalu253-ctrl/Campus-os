from sqlalchemy import select, desc

from app.extensions import db
from app.models import User
from app.pulse.models import CampusReport
from app.users import trust as trust_engine


def queue(*, limit: int = 50):
    """Reports needing moderator attention: high flags or low confidence."""
    stmt = (
        select(CampusReport)
        .where(CampusReport.moderation_status == "visible")
        .where(CampusReport.flag_count > 0)
        .order_by(desc(CampusReport.flag_count),
                  desc(CampusReport.reported_at))
        .limit(limit)
    )
    return db.session.execute(stmt).scalars().all()


def hide(report: CampusReport, *, reason: str = "") -> None:
    report.moderation_status = "hidden"
    reporter = db.session.get(User, report.reported_by) if report.reported_by else None
    if reporter:
        trust_engine.on_report_removed_by_moderation(reporter, hard=False)


def remove(report: CampusReport, *, reason: str = "") -> None:
    report.moderation_status = "removed"
    report.status = "removed"
    reporter = db.session.get(User, report.reported_by) if report.reported_by else None
    if reporter:
        trust_engine.on_report_removed_by_moderation(reporter, hard=True)


def restore(report: CampusReport) -> None:
    report.moderation_status = "visible"
    if report.status == "removed":
        report.status = "active"