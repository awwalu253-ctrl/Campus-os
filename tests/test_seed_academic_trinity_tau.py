"""Tests for the Trinity University and Thomas Adewumi University seed.

Covers the Phase 3.8A Step 1 behaviour:
  1. Normal seed creates both universities and one campus each.
  2. Idempotency — running twice produces no duplicates.
  3. Slug collision with a different name → warn + skip, no campus
     created, no overwrite.
  4. Coordinate fields are NULL after seed.
  5. Existing universities with the same slug and same name are
     skipped (not duplicated).

The seed's main() opens its own app context. Tests replicate the
insert logic inline (same pattern used by test_seed_universities.py
and test_seed_campus_coordinates.py) to keep the tests fast and
deterministic without subprocess/path gymnastics.
"""
import uuid

import pytest

from app.extensions import db
from app.models import University, Campus
from scripts.seed_academic_trinity_tau import SEED


def _run_seed():
    """Replicate the seed's insert logic inline.

    Same behaviour as the script: skip existing universities by slug
    with matching name, skip existing campuses by (university_id, slug),
    never overwrite, treat different-name slug collisions as skips.
    """
    for slug, name, short_name, state, campuses in SEED:
        existing = University.query.filter_by(slug=slug).first()

        if existing is not None:
            if existing.name != name:
                continue  # collision → skip
            university = existing
        else:
            university = University(
                slug=slug,
                name=name,
                short_name=short_name,
                state=state,
                is_active=True,
            )
            db.session.add(university)
            db.session.flush()

        for campus_slug, campus_name in campuses:
            dup = Campus.query.filter_by(
                university_id=university.id,
                slug=campus_slug,
            ).first()
            if dup is not None:
                continue
            db.session.add(Campus(
                university_id=university.id,
                slug=campus_slug,
                name=campus_name,
            ))
    db.session.commit()


# ── 1. Normal seed ────────────────────────────────────────
def test_seed_creates_trinity_and_tau(app):
    with app.app_context():
        _run_seed()

        trinity = University.query.filter_by(slug="trinity").one()
        assert trinity.name == "Trinity University, Yaba"
        assert trinity.short_name == "Trinity"
        assert trinity.state == "Lagos"
        assert trinity.is_active is True

        tau = University.query.filter_by(slug="tau").one()
        assert tau.name == "Thomas Adewumi University"
        assert tau.short_name == "TAU"
        assert tau.state == "Kwara"
        assert tau.is_active is True


# ── 2. Idempotency ────────────────────────────────────────
def test_seed_is_idempotent(app):
    with app.app_context():
        _run_seed()
        first_universities = University.query.count()
        first_campuses = Campus.query.count()
        assert first_universities == 2
        assert first_campuses == 2

        _run_seed()

        assert University.query.count() == first_universities
        assert Campus.query.count() == first_campuses


# ── 3. Slug collision with different name ────────────────
def test_seed_skips_slug_collision_with_different_name(app):
    with app.app_context():
        # Pre-create a different institution under the 'trinity' slug.
        other = University(
            slug="trinity",
            name="Trinity College Dublin",  # different institution
            short_name="TCD",
            state="Dublin",
            is_active=True,
        )
        db.session.add(other)
        db.session.commit()

        _run_seed()

        # The existing 'trinity' record must NOT be overwritten.
        stored = University.query.filter_by(slug="trinity").one()
        assert stored.name == "Trinity College Dublin"
        assert stored.state == "Dublin"

        # No campus was created for the collided slug.
        assert Campus.query.filter_by(university_id=other.id).count() == 0

        # TAU (unrelated) still got created.
        tau = University.query.filter_by(slug="tau").one()
        assert tau.name == "Thomas Adewumi University"
        assert Campus.query.filter_by(university_id=tau.id).count() == 1


# ── 4. Coordinates null ───────────────────────────────────
def test_seed_leaves_coordinates_null(app):
    with app.app_context():
        _run_seed()

        trinity_campus = Campus.query.filter_by(slug="yaba").one()
        assert trinity_campus.lat is None
        assert trinity_campus.lng is None

        tau_campus = Campus.query.filter_by(slug="oko").one()
        assert tau_campus.lat is None
        assert tau_campus.lng is None


# ── 5. Same-slug, same-name preservation ──────────────────
def test_seed_skips_existing_university_with_matching_name(app):
    """If a matching university already exists (same slug + same name),
    the seed must skip it without duplication — and must still create
    the campus if it's missing."""
    with app.app_context():
        uni = University(
            slug="trinity",
            name="Trinity University, Yaba",
            short_name="Trinity",
            state="Lagos",
            is_active=True,
        )
        db.session.add(uni)
        db.session.commit()

        _run_seed()

        # Still exactly one 'trinity' university.
        assert University.query.filter_by(slug="trinity").count() == 1
        # Its campus was created (was missing before).
        assert Campus.query.filter_by(
            university_id=uni.id, slug="yaba"
        ).count() == 1