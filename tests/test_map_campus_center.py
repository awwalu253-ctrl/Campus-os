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
from app.maps.models import Location



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

def _add_location_to_campus(campus_id, name="Test Location", category="building",
                            lat=8.5, lng=4.7, status="approved"):
    """Helper to insert a Location row for the given campus.

    Uses the WKT point convention shared with the rest of the codebase.
    Caller owns the transaction (this function does not commit).
    """
    wkt_point = f"SRID=4326;POINT({lng} {lat})"
    loc = Location(
        campus_id=campus_id,
        name=name,
        category=category,
        point=wkt_point,
        source="admin",
        status=status,
    )
    db.session.add(loc)
    db.session.flush()
    return loc


def _make_student_with_scenario(app, *, uni_slug, campus_slug, lat, lng,
                                with_location):
    """Create a student on a fresh university + campus under a given scenario.

    lat / lng — coords for the campus; pass None for "no coordinates".
    with_location — if True, insert one approved Location on the campus.
    """
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]

        uni = University(
            slug=f"{uni_slug}-{suffix}",
            name=f"Test {uni_slug.upper()} {suffix}",
            short_name=uni_slug.upper(),
            state="Test",
            is_active=True,
        )
        db.session.add(uni)
        db.session.flush()

        campus = Campus(
            university_id=uni.id,
            slug=campus_slug,
            name=f"Test Campus {suffix}",
            lat=lat,
            lng=lng,
        )
        db.session.add(campus)
        db.session.flush()

        if with_location:
            _add_location_to_campus(campus.id)

        u = auth_services.create_user(
            email=f"scenario-{suffix}@example.com",
            password="testpass1234",
            display_name="Scenario Test",
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
            "campus_id": campus.id,
            "campus_name": campus.name,
            "has_coords": lat is not None and lng is not None,
            "has_location": with_location,
        }


# ── Scenario A — coords + locations → map ────────────────
def test_unilag_student_sees_map_not_empty_state(app, client, unilag_student):
    _login(client, unilag_student)
    r = client.get("/map/")
    assert r.status_code == 200

    body = r.data
    # Map container is present.
    assert b'id="map"' in body
    # Empty state is NOT present.
    assert b"Map data isn't available for this campus yet." not in body


def test_unilorin_student_sees_map_not_empty_state(app, client, unilorin_student):
    _login(client, unilorin_student)
    r = client.get("/map/")
    assert r.status_code == 200

    body = r.data
    assert b'id="map"' in body
    assert b"Map data isn't available for this campus yet." not in body


# ── Scenario B — coords, no locations → map ──────────────
def test_campus_with_coords_but_no_locations_shows_map(app, client):
    ctx = _make_student_with_scenario(
        app,
        uni_slug="scenario-b",
        campus_slug="main",
        lat=8.5, lng=4.7,
        with_location=False,
    )
    _login(client, ctx["user_id"])
    r = client.get("/map/")
    assert r.status_code == 200

    body = r.data
    # Map renders (has coords, so no empty state).
    assert b'id="map"' in body
    assert b"Map data isn't available for this campus yet." not in body


# ── Scenario C — no coords, has locations → map ──────────
def test_campus_without_coords_but_with_locations_shows_map(app, client):
    """Requirement #5: missing coordinates alone does NOT trigger the
    empty state when approved locations exist."""
    ctx = _make_student_with_scenario(
        app,
        uni_slug="scenario-c",
        campus_slug="main",
        lat=None, lng=None,
        with_location=True,
    )
    _login(client, ctx["user_id"])
    r = client.get("/map/")
    assert r.status_code == 200

    body = r.data
    # Map still renders because there are locations.
    assert b'id="map"' in body
    assert b"Map data isn't available for this campus yet." not in body


# ── Scenario D — no coords, no locations → empty state ───
def test_campus_without_coords_or_locations_shows_empty_state(app, client):
    ctx = _make_student_with_scenario(
        app,
        uni_slug="scenario-d",
        campus_slug="main",
        lat=None, lng=None,
        with_location=False,
    )
    _login(client, ctx["user_id"])
    r = client.get("/map/")
    assert r.status_code == 200

    body = r.data
    # Empty state is rendered.
    assert b"Map data isn't available for this campus yet." in body
    assert b"Help build your campus map by suggesting a location." in body
    # Map container is NOT rendered.
    assert b'id="map"' not in body
    # map.js is NOT loaded.
    assert b"js/map.js" not in body


# ── Suggestion link in empty state ───────────────────────
def test_empty_state_contains_suggestion_link(app, client):
    ctx = _make_student_with_scenario(
        app,
        uni_slug="scenario-link",
        campus_slug="main",
        lat=None, lng=None,
        with_location=False,
    )
    _login(client, ctx["user_id"])
    r = client.get("/map/")
    assert r.status_code == 200

    body = r.data
    # The suggestion link is present with the correct text and URL.
    assert b"Suggest a location" in body
    assert b'href="/map/suggest"' in body


# ── Campus isolation preserved ───────────────────────────
def test_campus_isolation_preserved(app, client):
    """A student on campus A must never see campus B's locations
    in the API response, even with the empty-state logic in place."""
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]

        # Two separate universities + campuses + locations.
        uni_a = University(
            slug=f"iso-a-{suffix}", name=f"Iso A {suffix}",
            short_name="ISOA", state="Test", is_active=True,
        )
        uni_b = University(
            slug=f"iso-b-{suffix}", name=f"Iso B {suffix}",
            short_name="ISOB", state="Test", is_active=True,
        )
        db.session.add_all([uni_a, uni_b])
        db.session.flush()

        camp_a = Campus(university_id=uni_a.id, slug="main",
                        name="Campus A", lat=8.5, lng=4.7)
        camp_b = Campus(university_id=uni_b.id, slug="main",
                        name="Campus B", lat=6.5, lng=3.4)
        db.session.add_all([camp_a, camp_b])
        db.session.flush()

        loc_a = _add_location_to_campus(camp_a.id, name="Location On A")
        loc_b = _add_location_to_campus(camp_b.id, name="Location On B")

        u = auth_services.create_user(
            email=f"iso-{suffix}@example.com",
            password="testpass1234",
            display_name="Isolation Test",
        )
        u.profile = StudentProfile(
            user_id=u.id, university_id=uni_a.id, campus_id=camp_a.id,
        )
        db.session.add(u.profile)
        db.session.commit()

        sid = u.id

    _login(client, sid)
    r = client.get("/map/api/locations")
    assert r.status_code == 200

    data = r.get_json()
    names = [loc["name"] for loc in data["locations"]]
    assert "Location On A" in names
    assert "Location On B" not in names