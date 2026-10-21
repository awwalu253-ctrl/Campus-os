"""Tests for the map page's campus-center configuration.

The page exposes campus_lat / campus_lng via window.CAMPUS_OS. This
test file verifies:
  1. A UNILORIN student's page contains the UNILORIN coordinates.
  2. A UNILAG student's page contains the UNILAG coordinates.
  3. A student on a campus with no coordinates sees 'null' in the page.
  4. Unauthenticated access is redirected (existing behaviour, preserved).
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


def _make_student_with_campus(
    *, uni_slug, uni_name, campus_slug, campus_name, lat, lng
):
    """Create a university + campus (with optional coords) + student profile."""
    suffix = uuid.uuid4().hex[:8]

    uni = University(
        slug=uni_slug,
        name=f"{uni_name} {suffix}",
        short_name=uni_slug.upper(),
        state="Test",
        is_active=True,
    )
    db.session.add(uni)
    db.session.flush()

    campus = Campus(
        university_id=uni.id,
        slug=campus_slug,
        name=campus_name,
        lat=lat,
        lng=lng,
    )
    db.session.add(campus)
    db.session.flush()

    u = auth_services.create_user(
        email=f"student-{suffix}@example.com",
        password="testpass1234",
        display_name="Center Test",
    )
    u.profile = StudentProfile(
        user_id=u.id,
        university_id=uni.id,
        campus_id=campus.id,
    )
    db.session.add(u.profile)
    db.session.commit()

    return u.id


@pytest.fixture
def unilag_student(app):
    with app.app_context():
        return _make_student_with_campus(
            uni_slug="unilag",
            uni_name="University of Lagos",
            campus_slug="akoka",
            campus_name="Akoka Campus",
            lat=6.51821,
            lng=3.39556,
        )


@pytest.fixture
def unilorin_student(app):
    with app.app_context():
        return _make_student_with_campus(
            uni_slug="unilorin",
            uni_name="University of Ilorin",
            campus_slug="main",
            campus_name="Main Campus",
            lat=8.4826,
            lng=4.6736,
        )


@pytest.fixture
def no_coords_student(app):
    """Student on a campus with NULL coordinates — must fall back."""
    with app.app_context():
        return _make_student_with_campus(
            uni_slug="unn",
            uni_name="University of Nigeria",
            campus_slug="nsukka",
            campus_name="Nsukka Campus",
            lat=None,
            lng=None,
        )


def test_map_page_for_unilag_student_has_akoka_coords(
    app, client, unilag_student
):
    _login(client, unilag_student)
    r = client.get("/map/")
    assert r.status_code == 200

    body = r.data
    # The template emits the coordinates as numeric literals.
    assert b"campusLat: 6.51821" in body
    assert b"campusLng: 3.39556" in body


def test_map_page_for_unilorin_student_has_ilorin_coords(
    app, client, unilorin_student
):
    _login(client, unilorin_student)
    r = client.get("/map/")
    assert r.status_code == 200

    body = r.data
    assert b"campusLat: 8.4826" in body
    assert b"campusLng: 4.6736" in body


def test_map_page_for_null_coords_renders_null(app, client, no_coords_student):
    _login(client, no_coords_student)
    r = client.get("/map/")
    assert r.status_code == 200

    body = r.data
    # The template emits the literal keyword `null` for None values.
    assert b"campusLat: null" in body
    assert b"campusLng: null" in body


def test_map_page_requires_auth(client):
    r = client.get("/map/")
    # Flask-Login redirects unauthenticated users.
    assert r.status_code == 302