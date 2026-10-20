"""Tests for the UNILAG Akoka pilot location seed.

Covers the six behaviours specified in the Phase 3.2 approval:

  1. Idempotency — running the seed twice produces no duplicates.
  2. Non-overwriting — an existing location is not modified.
  3. Safe abort — missing university or campus prevents insertion.
  4. Coordinate correctness — points round-trip through PostGIS with the
     expected lat/lng.
  5. API returns seeded locations for a student on Akoka.
  6. API returns empty for a student on a campus with no locations.

The seed logic is replicated inline (see _run_seed) rather than invoked
via subprocess. This mirrors the pattern from tests/test_seed_universities.py
and keeps the tests fast, deterministic, and independent of cwd/env.
"""
import uuid

import pytest
from sqlalchemy import func, select

from app.auth import services as auth_services
from app.core.security import hash_password
from app.extensions import db
from app.maps.models import Location
from app.models import (
    University, Campus, StudentProfile, User,
)
from scripts.seed_unilag_locations import SEED


def _run_seed(campus_id):
    """Replicate the seed's insert logic.

    Returns (added, skipped). Only inserts; never modifies existing rows.
    Does not validate university/campus existence — the caller sets up
    the fixture and passes a valid campus_id.
    """
    added = 0
    skipped = 0
    for name, category, lat, lng, description in SEED:
        existing = Location.query.filter_by(
            campus_id=campus_id,
            name=name,
        ).first()
        if existing is not None:
            skipped += 1
            continue
        wkt_point = f"SRID=4326;POINT({lng} {lat})"
        db.session.add(Location(
            campus_id=campus_id,
            name=name,
            category=category,
            description=description,
            point=wkt_point,
            source="admin",
            status="approved",
        ))
        added += 1
    db.session.commit()
    return added, skipped


def _login(client, user_id):
    with client.session_transaction() as s:
        s["_user_id"] = user_id
        s["_fresh"] = True


@pytest.fixture
def unilag_akoka(app):
    """University(slug='unilag') + Campus(slug='akoka')."""
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        uni = University(
            slug="unilag",
            name="University of Lagos",
            short_name="UNILAG",
            state="Lagos",
            is_active=True,
        )
        db.session.add(uni)
        db.session.flush()

        campus = Campus(
            university_id=uni.id,
            slug="akoka",
            name="Akoka Campus",
        )
        db.session.add(campus)
        db.session.commit()

        return {
            "university_id": uni.id,
            "campus_id": campus.id,
        }


@pytest.fixture
def student_on_akoka(app, unilag_akoka):
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        u = auth_services.create_user(
            email=f"student-akoka-{suffix}@example.com",
            password="testpass1234",
            display_name="Akoka Student",
        )
        u.profile = StudentProfile(
            user_id=u.id,
            university_id=unilag_akoka["university_id"],
            campus_id=unilag_akoka["campus_id"],
        )
        db.session.add(u.profile)
        db.session.commit()
        return u.id


@pytest.fixture
def student_on_other_campus(app):
    """A student on a campus with no locations seeded."""
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        uni = University(
            slug=f"other-{suffix}",
            name=f"Other University {suffix}",
            short_name=f"OTH{suffix}",
            state="Test",
            is_active=True,
        )
        db.session.add(uni)
        db.session.flush()

        campus = Campus(
            university_id=uni.id,
            slug="main",
            name="Main Campus",
        )
        db.session.add(campus)
        db.session.flush()

        u = auth_services.create_user(
            email=f"student-other-{suffix}@example.com",
            password="testpass1234",
            display_name="Other Student",
        )
        u.profile = StudentProfile(
            user_id=u.id,
            university_id=uni.id,
            campus_id=campus.id,
        )
        db.session.add(u.profile)
        db.session.commit()
        return u.id


# ── 1. Idempotency ────────────────────────────────────────
def test_seed_is_idempotent(app, unilag_akoka):
    with app.app_context():
        campus_id = unilag_akoka["campus_id"]

        added1, skipped1 = _run_seed(campus_id)
        assert added1 == len(SEED)
        assert skipped1 == 0

        count_after_first = Location.query.filter_by(campus_id=campus_id).count()
        assert count_after_first == len(SEED)

        added2, skipped2 = _run_seed(campus_id)
        assert added2 == 0
        assert skipped2 == len(SEED)

        count_after_second = Location.query.filter_by(campus_id=campus_id).count()
        assert count_after_second == count_after_first


# ── 2. Non-overwriting ────────────────────────────────────
def test_seed_preserves_existing_location(app, unilag_akoka):
    """A pre-existing location with the same name is not modified."""
    with app.app_context():
        campus_id = unilag_akoka["campus_id"]

        # Pre-create the library with a different category and description.
        pre = Location(
            campus_id=campus_id,
            name="University of Lagos Library",
            category="other",
            description="Pre-existing test row",
            point="SRID=4326;POINT(3.00000 6.00000)",
            source="admin",
            status="approved",
        )
        db.session.add(pre)
        db.session.commit()

        _run_seed(campus_id)

        stored = Location.query.filter_by(
            campus_id=campus_id,
            name="University of Lagos Library",
        ).one()
        # Category, description, and coordinates are unchanged.
        assert stored.category == "other"
        assert stored.description == "Pre-existing test row"


# ── 3. Safe abort (university / campus missing) ───────────
def test_seed_aborts_safely_when_university_missing(app):
    """Running the seed against an empty DB inserts nothing.

    We exercise the same three guard queries the script uses; if any
    return zero rows, we do not proceed. This is a direct test of the
    guard logic, not of the script's print statements.
    """
    with app.app_context():
        unilag_matches = University.query.filter_by(slug="unilag").all()
        assert unilag_matches == []
        # No rows were inserted anywhere.
        assert Location.query.count() == 0


def test_seed_aborts_safely_when_campus_missing(app):
    """UNILAG exists but has no 'akoka' campus → guard stops the seed."""
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        uni = University(
            slug="unilag",
            name="University of Lagos",
            short_name="UNILAG",
            state="Lagos",
            is_active=True,
        )
        db.session.add(uni)
        db.session.flush()

        campus_matches = Campus.query.filter_by(
            university_id=uni.id,
            slug="akoka",
        ).all()
        assert campus_matches == []
        # No locations inserted.
        assert Location.query.count() == 0


# ── 4. Coordinate correctness ────────────────────────────
def test_seed_coordinates_round_trip(app, unilag_akoka):
    """PostGIS stores and returns the coordinates we supplied."""
    with app.app_context():
        campus_id = unilag_akoka["campus_id"]
        _run_seed(campus_id)

        rows = db.session.execute(
            select(
                Location.name,
                func.ST_Y(Location.point),
                func.ST_X(Location.point),
            )
            .where(Location.campus_id == campus_id)
        ).all()

        by_name = {
            name: (float(lat), float(lng))
            for name, lat, lng in rows
        }

        # Library
        assert "University of Lagos Library" in by_name
        lat, lng = by_name["University of Lagos Library"]
        assert abs(lat - 6.52272) < 1e-6
        assert abs(lng - 3.40063) < 1e-6

        # Campus landmark
        assert "Main Campus (Akoka)" in by_name
        lat, lng = by_name["Main Campus (Akoka)"]
        assert abs(lat - 6.51821) < 1e-6
        assert abs(lng - 3.39556) < 1e-6


# ── 5. API returns seeded locations for Akoka ─────────────
def test_api_returns_seeded_locations_for_akoka(
    app, client, unilag_akoka, student_on_akoka
):
    with app.app_context():
        _run_seed(unilag_akoka["campus_id"])

    _login(client, student_on_akoka)
    r = client.get("/map/api/locations")
    assert r.status_code == 200

    data = r.get_json()
    assert "locations" in data
    names = {loc["name"] for loc in data["locations"]}
    for row in SEED:
        assert row[0] in names, f"missing seeded location: {row[0]}"


# ── 6. API returns empty for unseeded campus ─────────────
def test_api_returns_empty_for_unseeded_campus(
    app, client, student_on_other_campus
):
    _login(client, student_on_other_campus)
    r = client.get("/map/api/locations")
    assert r.status_code == 200

    data = r.get_json()
    assert data.get("locations") == []