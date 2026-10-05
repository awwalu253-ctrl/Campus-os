"""Data-driven Pulse category registry.

Adding a new category should NEVER require a migration.
Add it here and restart.
"""

CATEGORIES = {
    # ── Utilities ────────────────────────────────────────
    "power_available": {
        "group": "Utilities",
        "label": "Electricity available",
        "status": "green",
        "default_ttl_min": 120,
    },
    "power_outage": {
        "group": "Utilities",
        "label": "Electricity outage",
        "status": "red",
        "default_ttl_min": 90,
    },
    "water_available": {
        "group": "Utilities",
        "label": "Water available",
        "status": "green",
        "default_ttl_min": 240,
    },
    "water_outage": {
        "group": "Utilities",
        "label": "Water outage",
        "status": "red",
        "default_ttl_min": 180,
    },
    "network_down": {
        "group": "Utilities",
        "label": "Network issues",
        "status": "amber",
        "default_ttl_min": 60,
    },

    # ── Queues ───────────────────────────────────────────
    "queue_short": {
        "group": "Queues",
        "label": "Queue is short",
        "status": "green",
        "default_ttl_min": 30,
    },
    "queue_long": {
        "group": "Queues",
        "label": "Queue is long",
        "status": "amber",
        "default_ttl_min": 30,
    },
    "atm_available": {
        "group": "Queues",
        "label": "ATM working",
        "status": "green",
        "default_ttl_min": 60,
    },
    "atm_down": {
        "group": "Queues",
        "label": "ATM not working",
        "status": "red",
        "default_ttl_min": 60,
    },

    # ── Transport ────────────────────────────────────────
    "traffic_clear": {
        "group": "Transport",
        "label": "Road clear",
        "status": "green",
        "default_ttl_min": 30,
    },
    "traffic_heavy": {
        "group": "Transport",
        "label": "Heavy traffic",
        "status": "amber",
        "default_ttl_min": 30,
    },
    "shuttle_available": {
        "group": "Transport",
        "label": "Shuttle available",
        "status": "green",
        "default_ttl_min": 20,
    },
    "shuttle_unavailable": {
        "group": "Transport",
        "label": "No shuttle",
        "status": "red",
        "default_ttl_min": 30,
    },

    # ── Facilities ───────────────────────────────────────
    "classroom_free": {
        "group": "Facilities",
        "label": "Classroom free",
        "status": "green",
        "default_ttl_min": 60,
    },
    "classroom_full": {
        "group": "Facilities",
        "label": "Classroom occupied",
        "status": "amber",
        "default_ttl_min": 60,
    },
    "library_busy": {
        "group": "Facilities",
        "label": "Library busy",
        "status": "amber",
        "default_ttl_min": 120,
    },
    "lab_unavailable": {
        "group": "Facilities",
        "label": "Lab unavailable",
        "status": "red",
        "default_ttl_min": 120,
    },
    "restroom_issue": {
        "group": "Facilities",
        "label": "Restroom issue",
        "status": "amber",
        "default_ttl_min": 120,
    },

    # ── Environment ──────────────────────────────────────
    "flooding": {
        "group": "Environment",
        "label": "Flooding",
        "status": "red",
        "default_ttl_min": 180,
    },
    "blocked_road": {
        "group": "Environment",
        "label": "Road blocked",
        "status": "red",
        "default_ttl_min": 120,
    },
    "construction": {
        "group": "Environment",
        "label": "Construction",
        "status": "amber",
        "default_ttl_min": 480,
    },
    "unusual_crowd": {
        "group": "Environment",
        "label": "Unusual crowd",
        "status": "amber",
        "default_ttl_min": 90,
    },

    # ── Safety ───────────────────────────────────────────
    "suspicious_activity": {
        "group": "Safety",
        "label": "Suspicious activity",
        "status": "red",
        "default_ttl_min": 60,
    },
    "dangerous_area": {
        "group": "Safety",
        "label": "Dangerous area",
        "status": "red",
        "default_ttl_min": 240,
    },
    "emergency": {
        "group": "Safety",
        "label": "Emergency",
        "status": "red",
        "default_ttl_min": 30,
    },
}


def get(key: str) -> dict | None:
    return CATEGORIES.get(key)


def groups() -> dict[str, list[dict]]:
    """Return categories grouped by their 'group' field, for UI rendering."""
    grouped: dict[str, list[dict]] = {}
    for key, meta in CATEGORIES.items():
        grouped.setdefault(meta["group"], []).append({"key": key, **meta})
    for items in grouped.values():
        items.sort(key=lambda x: x["label"])
    return grouped


def is_valid(key: str) -> bool:
    return key in CATEGORIES