# ── Pulse ──────────────────────────────────────────────
REPORT_CONFIRMATION_MILESTONE = "report_confirmation_milestone"
REPORT_DISAGREEMENT = "report_disagreement"
REPORT_FLAGGED = "report_flagged"
REPORT_EXPIRED_STALE = "report_expired_stale"

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