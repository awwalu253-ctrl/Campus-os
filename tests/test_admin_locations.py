"""Tests for the admin Campus Locations pages.

Covers the read-only list and detail views at /admin/locations.
These tests assert:
  1. Auth is required.
  2. Permissions are enforced.
  3. The list renders for a platform admin.
  4. The detail view renders for an existing location.

The pages are strictly read-only: no edit form, no delete, no status
toggle. Any future mutation would be a separate, deliberate change.
"""
import uuid

import pytest

from app.core.security import hash_password
from app.extensions import db
from app.maps.models import Location
from app.models import Campus, University, User


@pytest.fixture
def admin(app):
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        u = User(
            email=f"admin-{suffix}@example.com",
            display_name="Admin",
            password_hash=hash_password("testpass1234"),
            role="platform_admin",
            status="active",
        )
        db.session.add(u)
        db.session.commit()
        return u.id


@pytest.fixture
def location_with_campus(app):
    """Create one University + Campus + Location.

    Returns a dict of ids. Coordinates are placed inside the UNILORIN
    area so they're syntactically consistent with real seed data.
    """
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]

        uni = University(
            slug=f"loc-test-{suffix}",
            name=f"Loc Test {suffix}",
            short_name=f"LT{suffix}",
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

        lat, lng = 8.4826, 4.6736
        wkt_point = f"SRID=4326;POINT({lng} {lat})"

        loc = Location(
            campus_id=campus.id,
            name="Test Library",
            category="library",
            description="A test library",
            point=wkt_point,
            source="admin",
            status="approved",
        )
        db.session.add(loc)
        db.session.commit()

        return {
            "campus_id": campus.id,
            "location_id": loc.id,
            "location_name": "Test Library",
        }


def _login(client, user_id):
    with client.session_transaction() as s:
        s["_user_id"] = user_id
        s["_fresh"] = True


def test_admin_locations_requires_auth(client):
    r = client.get("/admin/locations")
    assert r.status_code == 302


def test_admin_locations_requires_admin(app, client):
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        u = User(
            email=f"student-{suffix}@example.com",
            display_name="Student",
            password_hash=hash_password("testpass1234"),
            role="student",
            status="active",
        )
        db.session.add(u)
        db.session.commit()
        sid = u.id
    _login(client, sid)
    r = client.get("/admin/locations")
    assert r.status_code == 403


def test_admin_locations_renders_for_admin(app, client, admin):
    _login(client, admin)
    r = client.get("/admin/locations")
    assert r.status_code == 200

    body = r.data
    # The list page uses "Campus Locations" in both the H1 and the
    # breadcrumb. The filter labels are unique to this page.
    for label in (b"Campus Locations", b"Category", b"Campus", b"Source", b"Search"):
        assert label in body, f"missing label: {label}"


def test_admin_locations_detail_renders_for_admin(
    app, client, admin, location_with_campus
):
    _login(client, admin)
    loc_id = location_with_campus["location_id"]
    r = client.get(f"/admin/locations/{loc_id}")
    assert r.status_code == 200

    body = r.data
    # The location name should appear in the H1 and breadcrumb.
    assert location_with_campus["location_name"].encode() in body
    # The category label should be resolved from the registry.
    assert b"Library" in body