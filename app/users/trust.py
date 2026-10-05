"""Trust scoring for Campus Pulse.

Rules:
- New users start at 0 / 'new'.
- Confirmed-accurate reports reward the reporter slowly.
- Disagreed or flagged reports penalize.
- Confirmations a user gives that later prove correct reward them too.
- Tier thresholds are conservative.
"""

from app.extensions import db
from app.models import User, TrustScore


TIER_THRESHOLDS = [
    ("highly_trusted", 500),
    ("trusted", 150),
    ("community", 40),
    ("new", 0),
]


def _tier_for(score: int) -> str:
    for name, threshold in TIER_THRESHOLDS:
        if score >= threshold:
            return name
    return "new"


def get_or_create(user: User) -> TrustScore:
    if user.trust is None:
        user.trust = TrustScore()
        db.session.add(user.trust)
        db.session.flush()
    return user.trust


def adjust(user: User, *, delta: int,
           accurate: int = 0, false: int = 0,
           confirmations_given: int = 0, confirmations_received: int = 0,
           abuse: int = 0) -> TrustScore:
    ts = get_or_create(user)
    ts.score = max(0, ts.score + delta)
    ts.accurate_reports += accurate
    ts.false_reports += false
    ts.confirmations_given += confirmations_given
    ts.confirmations_received += confirmations_received
    ts.abuse_flags += abuse
    ts.tier = _tier_for(ts.score)
    return ts


# ── Named events that touch trust ─────────────────────────
def on_report_created(user: User) -> None:
    """Creating a report is neutral by itself — no trust change yet."""


def on_report_confirmed(user: User, *, weight: int = 1) -> None:
    """Another user confirmed this report; reporter gets credit."""
    adjust(user, delta=1 * weight, accurate=1, confirmations_received=1)


def on_report_disagreed(user: User) -> None:
    adjust(user, delta=-2, false=1)


def on_report_flagged(user: User) -> None:
    adjust(user, delta=-5, abuse=1)


def on_report_removed_by_moderation(user: User, *, hard: bool = False) -> None:
    adjust(user, delta=-15 if hard else -5, false=1 if hard else 0)


def on_confirmation_given(confirmer: User, *, agreed_with_majority: bool) -> None:
    if agreed_with_majority:
        adjust(confirmer, delta=1, confirmations_given=1)
    else:
        adjust(confirmer, delta=-1, confirmations_given=1)