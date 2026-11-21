"""Provisioning script for the General Campus Area location.

Idempotent. Safe to run multiple times. Refuses to run in production,
refuses unknown FLASK_ENV values, and refuses to invent or fall back to
any coordinates. Must be invoked explicitly:

    python -m scripts.provision_campus_area <campus_id>

This module is intentionally not wired into app startup, seed scripts,
or any route. It is a manual operator tool.
"""
import os
import sys

from sqlalchemy.exc import SQLAlchemyError

from app import create_app
from app.extensions import db
from app.models import Campus
from app.maps.models import Location
from app.maps import services as map_services


GENERAL_AREA_NAME = "General Campus Area"
GENERAL_AREA_DESCRIPTION = "Approximate center of the campus."
ALLOWED_ENVS = ("development", "testing")


def _check_environment() -> None:
    """Refuse anything that is not explicitly development or testing.

    No override. Production and any unknown/missing value are rejected.
    """
    env = os.getenv("FLASK_ENV")
    if env not in ALLOWED_ENVS:
        print(
            f"Refusing to run: FLASK_ENV={env!r} is not one of {ALLOWED_ENVS}. "
            "This provisioning script must not run in production."
        )
        sys.exit(1)


def _validate_coordinates(campus: Campus) -> tuple[float, float] | None:
    """Return (lat, lng) as floats, or None if missing/invalid/out-of-bounds."""
    lat_raw = campus.lat
    lng_raw = campus.lng

    if lat_raw is None or lng_raw is None:
        print(
            f"Refusing to provision: campus {campus.id} "
            f"({campus.name!r}) has no coordinates (lat/lng)."
        )
        return None

    try:
        lat = float(lat_raw)
        lng = float(lng_raw)
    except (TypeError, ValueError):
        print(
            f"Refusing to provision: campus {campus.id} "
            f"has non-numeric coordinates (lat={lat_raw!r}, lng={lng_raw!r})."
        )
        return None

    if not (-90.0 <= lat <= 90.0):
        print(
            f"Refusing to provision: campus {campus.id} latitude {lat} "
            "is outside [-90, 90]."
        )
        return None
    if not (-180.0 <= lng <= 180.0):
        print(
            f"Refusing to provision: campus {campus.id} longitude {lng} "
            "is outside [-180, 180]."
        )
        return None

    return lat, lng


def ensure_general_campus_area(campus_id: str) -> Location | None:
    """Ensure a General Campus Area location exists for `campus_id`.

    Returns:
        The Location (newly created or already existing), or None on any
        refusal or DB error. Never overwrites an existing record.
    """
    campus = db.session.get(Campus, campus_id)
    if campus is None:
        print(f"Error: campus with id {campus_id!r} does not exist.")
        return None

    coords = _validate_coordinates(campus)
    if coords is None:
        return None
    lat, lng = coords

    existing = Location.query.filter_by(
        campus_id=campus.id, name=GENERAL_AREA_NAME
    ).first()
    if existing is not None:
        print(
            f"General Campus Area already exists for campus {campus.id} "
            f"(location id {existing.id}). No action taken."
        )
        return existing

    try:
        loc = map_services.create_location(
            campus_id=campus.id,
            name=GENERAL_AREA_NAME,
            category="landmark",
            lat=lat,
            lng=lng,
            description=GENERAL_AREA_DESCRIPTION,
            source="admin",
            status="approved",
        )
        db.session.commit()
        print(
            f"Created General Campus Area for campus {campus.id} "
            f"(location id {loc.id})."
        )
        return loc
    except (SQLAlchemyError, ValueError) as exc:
        db.session.rollback()
        print(f"Provisioning failed for campus {campus.id}: {exc}")
        return None


def _main(argv: list[str]) -> int:
    _check_environment()

    if len(argv) != 2:
        print("Usage: python -m scripts.provision_campus_area <campus_id>")
        return 1

    campus_id = argv[1].strip()
    if not campus_id:
        print("Error: campus_id must be a non-empty string.")
        return 1

    app = create_app()
    with app.app_context():
        loc = ensure_general_campus_area(campus_id)
        return 0 if loc is not None else 1


if __name__ == "__main__":
    sys.exit(_main(sys.argv))