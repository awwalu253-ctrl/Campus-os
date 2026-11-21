"""Tests for scripts/provision_campus_area.py (Phase 2, Step 1)."""
import uuid

import pytest

from app.extensions import db
from app.models import Campus, University
from app.maps.models import Location
from app.maps.services import create_location
from scripts.provision_campus_area import (
    GENERAL_AREA_NAME,
    ensure_general_campus_area,
)


def _make_campus(app, *, lat=8.4920, lng=4.6736):
    """Create a University + Campus with the given coordinates. Returns campus.id."""
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        uni = University(
            slug=f"test-uni-{suffix}",
            name=f"Test University {suffix}",
            short_name="TU",
            state="Test",
        )
        db.session.add(uni)
        db.session.flush()

        campus = Campus(
            university_id=uni.id,
            slug=f"main-{suffix}",
            name=f"Test Campus {suffix}",
            lat=lat,
            lng=lng,
        )
        db.session.add(campus)
        db.session.commit()
        return campus.id


# 1. Creates a General Campus Area when coordinates are valid.
def test_creates_general_campus_area_with_valid_coords(app):
    with app.app_context():
        campus_id = _make_campus(app)

        loc = ensure_general_campus_area(campus_id)

        assert loc is not None
        assert loc.name == GENERAL_AREA_NAME
        assert loc.category == "landmark"
        assert loc.status == "approved"
        assert loc.source == "admin"
        assert loc.campus_id == campus_id

        count = Location.query.filter_by(
            campus_id=campus_id, name=GENERAL_AREA_NAME
        ).count()
        assert count == 1


# 2. Idempotent: running twice does not create duplicates.
def test_idempotent_does_not_duplicate(app):
    with app.app_context():
        campus_id = _make_campus(app)

        first = ensure_general_campus_area(campus_id)
        second = ensure_general_campus_area(campus_id)

        assert first is not None
        assert second is not None
        assert first.id == second.id

        count = Location.query.filter_by(
            campus_id=campus_id, name=GENERAL_AREA_NAME
        ).count()
        assert count == 1


# 3. Refuses when campus coordinates are missing.
def test_refuses_when_coords_missing(app):
    with app.app_context():
        campus_id = _make_campus(app, lat=None, lng=None)

        loc = ensure_general_campus_area(campus_id)
        assert loc is None

        count = Location.query.filter_by(
            campus_id=campus_id, name=GENERAL_AREA_NAME
        ).count()
        assert count == 0


# 4. Refuses gracefully when the campus does not exist.
def test_handles_nonexistent_campus(app):
    with app.app_context():
        missing_id = str(uuid.uuid4())
        loc = ensure_general_campus_area(missing_id)
        assert loc is None


# 5. Preserves an existing record without overwriting it.
def test_preserves_existing_record_without_overwriting(app):
    with app.app_context():
        campus_id = _make_campus(app)

        # Pre-create a location with the same name but different category.
        existing = create_location(
            campus_id=campus_id,
            name=GENERAL_AREA_NAME,
            category="other",
            lat=10.0,
            lng=10.0,
            description="Pre-existing description that must survive.",
            source="admin",
            status="approved",
        )
        db.session.commit()
        existing_id = existing.id

        loc = ensure_general_campus_area(campus_id)

        assert loc is not None
        assert loc.id == existing_id
        assert loc.category == "other"
        assert loc.description == "Pre-existing description that must survive."

        count = Location.query.filter_by(
            campus_id=campus_id, name=GENERAL_AREA_NAME
        ).count()
        assert count == 1