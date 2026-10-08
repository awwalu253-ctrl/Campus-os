# ── Pulse ──────────────────────────────────────────────
REPORT_CONFIRMATION_MILESTONE = "report_confirmation_milestone"
REPORT_DISAGREEMENT = "report_disagreement"
REPORT_FLAGGED = "report_flagged"
REPORT_EXPIRED_STALE = "report_expired_stale"
CAMPUS_SAFETY_REPORT = "campus_safety_report"

# ── Locations ──────────────────────────────────────────
LOCATION_SUGGESTION_APPROVED = "location_suggestion_approved"
LOCATION_SUGGESTION_REJECTED = "location_suggestion_rejected"


# ── Confirmation milestone policy ─────────────────────
CONFIRMATION_MILESTONES = frozenset({1, 5, 10, 25, 50})


# ── Registry ───────────────────────────────────────────
REGISTRY = {
    REPORT_CONFIRMATION_MILESTONE: {
        "label": "Report confirmation milestone",
        "category": "pulse",
    },
    REPORT_DISAGREEMENT: {
        "label": "Report disagreement",
        "category": "pulse",
    },
    REPORT_FLAGGED: {
        "label": "Report flagged",
        "category": "pulse",
    },
    REPORT_EXPIRED_STALE: {
        "label": "Report expired without confirmation",
        "category": "pulse",
    },
    CAMPUS_SAFETY_REPORT: {
        "label": "Campus-wide safety report",
        "category": "pulse",
    },
    LOCATION_SUGGESTION_APPROVED: {
        "label": "Location suggestion approved",
        "category": "locations",
    },
    LOCATION_SUGGESTION_REJECTED: {
        "label": "Location suggestion rejected",
        "category": "locations",
    },
}


def is_valid(key: str) -> bool:
    return key in REGISTRY


def meta(key: str) -> dict | None:
    return REGISTRY.get(key)

# ── Campus-notifiable category groups ──────────────────
# Only reports in these groups trigger a campus-wide notification
# when a new report is created. Ordinary reports do not.
CAMPUS_NOTIFY_GROUPS = frozenset({"Safety", "Environment"})


def is_campus_notifiable(category_key: str) -> bool:
    """True if a report in this category should notify the campus.

    Looks up the category in the Pulse registry, reads its group,
    and checks against CAMPUS_NOTIFY_GROUPS. Imported lazily to avoid
    a circular import between notifications and pulse.
    """
    from app.pulse import categories as pulse_categories
    meta = pulse_categories.get(category_key)
    if not meta:
        return False
    return meta.get("group") in CAMPUS_NOTIFY_GROUPS