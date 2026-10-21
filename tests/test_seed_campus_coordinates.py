"""Tests for the campus coordinate seed script.

Covers the behaviour that matters for safe, idempotent coordinate seeding:

  1. Idempotency — running twice produces no duplicates and no changes.
  2. Preservation — pre-populated campuses are not overwritten.
  3. Missing university — the seed logs and skips, does not abort.
  4. Missing campus — same.
  5. Coordinate exactness — the two verified values land in the DB.
"""
import uuid

import pytest

from app.extensions import db
from app.models import University, Campus
from scripts.seed_campus_coordinates import SEED


def _run_seed():
    """Replicate the seed's insert logic inline.

    Same pattern as test_seed_universities.py — import the SEED constant
    from the script, reproduce the loop. Tests exercise behaviour without
    subprocess machinery.
    """
    for uni_slug, campus_slug, lat, lng in SEED:
        university = University.query.filter_by(slug=uni_slug).first()
        if university is None:
            continue
        campus = Campus.query.filter_by(
            university_id=university.id, slug=campus_slug
        ).first()
        if campus is None:
            continue
        if campus.lat is not None or campus.lng is not None:
            continue
        campus.lat = lat
        campus.lng = lng
    db.session.commit()


@pytest.fixture
def unilag_akoka(app):
    """A fresh UNILAG/Akoka pair with no coordinates."""
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        uni = University(
            slug="unilag",
            name=f"University of Lagos {suffix}",
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
        return {"university_id": uni.id, "campus_id": campus.id}


@pytest.fixture
def unilorin_main(app):
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        uni = University(
            slug="unilorin",
            name=f"University of Ilorin {suffix}",
            short_name="UNILORIN",
            state="Kwara",
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
        db.session.commit()
        return {"university_id": uni.id, "campus_id": campus.id}


# ── 1. Idempotency ────────────────────────────────────────
def test_seed_is_idempotent(app, unilag_akoka, unilorin_main):
    with app.app_context():
        _run_seed()

        unilag = db.session.get(Campus, unilag_akoka["campus_id"])
        unilorin = db.session.get(Campus, unilorin_main["campus_id"])
        assert unilag.lat == 6.51821
        assert unilag.lng == 3.39556
        assert unilorin.lat == 8.4826
        assert unilorin.lng == 4.6736

        # Run again — values must not change.
        _run_seed()
        assert db.session.get(Campus, unilag_akoka["campus_id"]).lat == 6.51821
        assert db.session.get(Campus, unilorin_main["campus_id"]).lat == 8.4826


# ── 2. Preservation ───────────────────────────────────────
def test_seed_does_not_overwrite_populated_campus(app, unilag_akoka):
    with app.app_context():
        # Pre-set a custom coordinate on Akoka.
        campus = db.session.get(Campus, unilag_akoka["campus_id"])
        campus.lat = 1.0
        campus.lng = 2.0
        db.session.commit()

        _run_seed()

        # The seed must NOT overwrite the pre-set values.
        stored = db.session.get(Campus, unilag_akoka["campus_id"])
        assert stored.lat == 1.0
        assert stored.lng == 2.0


# ── 3. Missing university ─────────────────────────────────
def test_seed_skips_missing_university(app):
    """No UNILAG in DB → the unilag/akoka entry skips silently, unilorin
    entry also skips (no unilorin university). No exceptions, no rows
    touched."""
    with app.app_context():
        # Empty DB — no universities at all.
        _run_seed()  # Must not raise.
        assert Campus.query.count() == 0


# ── 4. Missing campus ─────────────────────────────────────
def test_seed_skips_missing_campus(app):
    """University exists but campus doesn't → the entry is skipped,
    no partial writes."""
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        uni = University(
            slug="unilag",
            name=f"University of Lagos {suffix}",
            short_name="UNILAG",
            state="Lagos",
            is_active=True,
        )
        db.session.add(uni)
        db.session.commit()

        _run_seed()  # Akoka doesn't exist → skip.

        assert Campus.query.filter_by(university_id=uni.id).count() == 0


# ── 5. Coordinate exactness ───────────────────────────────
def test_seed_coordinates_match_seed_values(app, unilag_akoka, unilorin_main):
    with app.app_context():
        _run_seed()

        for uni_slug, campus_slug, lat, lng in SEED:
            uni = University.query.filter_by(slug=uni_slug).one()
            campus = Campus.query.filter_by(
                university_id=uni.id, slug=campus_slug
            ).one()
            assert campus.lat == lat, f"{uni_slug}/{campus_slug} lat mismatch"
            assert campus.lng == lng, f"{uni_slug}/{campus_slug} lng mismatch"