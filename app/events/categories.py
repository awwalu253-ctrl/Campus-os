
"""Canonical categories for campus events."""

EVENT_CATEGORIES = {
    "academic": "Academic",
    "arts_culture": "Arts & Culture",
    "career": "Career & Networking",
    "community": "Community",
    "sports_fitness": "Sports & Fitness",
    "technology": "Technology",
    "social": "Social",
    "workshop": "Workshop",
    "other": "Other",
}


def is_valid(key: str) -> bool:
    return key in EVENT_CATEGORIES


def all_categories() -> list[dict]:
    return [
        {"key": key, "label": label}
        for key, label in EVENT_CATEGORIES.items()
    ]
