"""Data-driven location category registry. Adding categories
should not require a migration."""

LOCATION_CATEGORIES = {
    "building":      {"label": "Building",        "icon": "building"},
    "lecture_hall":  {"label": "Lecture Hall",    "icon": "graduation-cap"},
    "library":       {"label": "Library",         "icon": "book-open"},
    "lab":           {"label": "Laboratory",      "icon": "flask-conical"},
    "admin_office":  {"label": "Admin Office",    "icon": "briefcase"},
    "hostel":        {"label": "Hostel",          "icon": "home"},
    "cafeteria":     {"label": "Cafeteria",       "icon": "utensils"},
    "restaurant":    {"label": "Restaurant",      "icon": "utensils-crossed"},
    "shop":          {"label": "Shop",            "icon": "shopping-bag"},
    "atm":           {"label": "ATM",             "icon": "banknote"},
    "bank":          {"label": "Bank",            "icon": "landmark"},
    "printing":      {"label": "Printing",        "icon": "printer"},
    "pharmacy":      {"label": "Pharmacy",        "icon": "pill"},
    "clinic":        {"label": "Clinic",          "icon": "stethoscope"},
    "transport":     {"label": "Transport",       "icon": "bus"},
    "parking":       {"label": "Parking",         "icon": "square-parking"},
    "worship":       {"label": "Worship",         "icon": "church"},
    "sports":        {"label": "Sports Facility", "icon": "dumbbell"},
    "landmark":      {"label": "Landmark",        "icon": "map-pin"},
    "other":         {"label": "Other",           "icon": "circle"},
}


def is_valid(key: str) -> bool:
    return key in LOCATION_CATEGORIES


def all_categories():
    return [{"key": k, **v} for k, v in LOCATION_CATEGORIES.items()]