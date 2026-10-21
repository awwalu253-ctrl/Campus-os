"""Tests for the student profile page's read-only academic placement display.

Covers:
  1. An onboarded student sees their university and campus names (with
     the university's state appended when present).
  2. A student whose profile has no campus set sees an em dash for the
     campus row.
  3. Unauthenticated access redirects to login.
"""
import uuid

import pytest

from app.auth import services as auth_services
from app.extensions import db
from app.models import University, Campus, StudentProfile


def _login(client, user_id):
    with client.session_transaction() as s:
        s["_user_id"] = user_id
        s["_fresh"] = True


@pytest.fixture
def student_with_full_profile(app):
    """A student with university, campus, and state all set."""
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]

        uni = University(
            slug=f"test-uni-{suffix}",
            name=f"Test University {suffix}",
            short_name=f"TU{suffix}",
            state="Test State",
            is_active=True,
        )
        db.session.add(uni)
        db.session.flush()

        campus = Campus(
            university_id=uni.id,
            slug="main",
            name=f"Test Campus {suffix}",
        )
        db.session.add(campus)
        db.session.flush()

        u = auth_services.create_user(
            email=f"profile-{suffix}@example.com",
            password="testpass1234",
            display_name="Profile Test",
        )
        u.profile = StudentProfile(
            user_id=u.id,
            university_id=uni.id,
            campus_id=campus.id,
        )
        db.session.add(u.profile)
        db.session.commit()

        return {
            "user_id": u.id,
            "university_name": uni.name,
            "university_state": uni.state,
            "campus_name": campus.name,
        }


@pytest.fixture
def student_without_campus(app):
    """A student with a university but no campus set."""
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]

        uni = University(
            slug=f"nocampus-{suffix}",
            name=f"No Campus University {suffix}",
            short_name=f"NC{suffix}",
            state=None,
            is_active=True,
        )
        db.session.add(uni)
        db.session.flush()

        u = auth_services.create_user(
            email=f"nocampus-{suffix}@example.com",
            password="testpass1234",
            display_name="No Campus Test",
        )
        u.profile = StudentProfile(
            user_id=u.id,
            university_id=uni.id,
            campus_id=None,
        )
        db.session.add(u.profile)
        db.session.commit()

        return {
            "user_id": u.id,
            "university_name": uni.name,
        }


# ── 1. Full profile ───────────────────────────────────────
def test_profile_shows_university_and_campus(app, client, student_with_full_profile):
    _login(client, student_with_full_profile["user_id"])
    r = client.get("/me/profile")
    assert r.status_code == 200

    body = r.data
    # The university name appears (with state appended).
    assert student_with_full_profile["university_name"].encode() in body
    assert student_with_full_profile["university_state"].encode() in body
    # The campus name appears.
    assert student_with_full_profile["campus_name"].encode() in body


# ── 2. Missing campus ─────────────────────────────────────
def test_profile_shows_em_dash_when_campus_missing(app, client, student_without_campus):
    _login(client, student_without_campus["user_id"])
    r = client.get("/me/profile")
    assert r.status_code == 200

    body = r.data
    # The university still shows.
    assert student_without_campus["university_name"].encode() in body
    # The em dash (U+2014) is present somewhere in the rendered output —
    # this is the "no campus" placeholder. Note: other em dashes may
    # exist elsewhere on the page, so this is a weak positive; the
    # stronger guarantee is the next assertion.
    assert "—".encode("utf-8") in body
    # The "Campus" label is present in the profile list (not just as a
    # word anywhere on the page).
    assert b"<span>Campus</span>" in body


# ── 3. Auth required ──────────────────────────────────────
def test_profile_requires_auth(client):
    r = client.get("/me/profile")
    assert r.status_code == 302