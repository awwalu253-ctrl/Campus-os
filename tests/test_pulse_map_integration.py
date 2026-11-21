"""Step 2 integration tests — Pulse reports default to General Campus Area.

Scope:
  - Default assignment when no location is provided.
  - Explicit location preserved.
  - Fallback to NULL when no General Campus Area exists.
  - Campus isolation (default belongs to user's campus).
  - /map/api/pulse includes reports defaulted to the General Campus Area,
    authenticated as a user on the intended campus, with isolation from
    any pre-existing reports.
  - Duplicate General Campus Area -> fallback to NULL (safeguard).
"""
import uuid

import pytest

from app.extensions import db
from app.models import Campus, University, User, StudentProfile
from app.maps.models import Location
from app.maps.services import create_location
from app.pulse.models import CampusReport
from app.pulse import categories as pulse_categories
from app.auth import services as auth_services


# ── Helpers ────────────────────────────────────────────────
def _make_campus(app, *, with_gca=True, gca_category="landmark",
                 gca_lat=8.4920, gca_lng=4.6736):
    """Create University + Campus, optionally provisioning a General Campus Area.

    Returns (campus_id, university_id, gc_id_or_None).
    """
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        uni = University(
            slug=f"uni-{suffix}", name=f"Uni {suffix}",
            short_name="TU", state="Test",
        )
        db.session.add(uni)
        db.session.flush()
        university_id = uni.id

        campus = Campus(
            university_id=uni.id, slug=f"main-{suffix}",
            name=f"Campus {suffix}", lat=gca_lat, lng=gca_lng,
        )
        db.session.add(campus)
        db.session.flush()

        gc_id = None
        if with_gca:
            gc = create_location(
                campus_id=campus.id,
                name="General Campus Area",
                category=gca_category,
                lat=gca_lat,
                lng=gca_lng,
                source="admin",
                status="approved",
            )
            gc_id = gc.id

        db.session.commit()
        return campus.id, university_id, gc_id


def _make_user(app, campus_id, university_id):
    """Create a student user with a profile on the given campus."""
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        user = auth_services.create_user(
            email=f"pulse-{suffix}@example.com",
            password="testpass1234",
            display_name="Pulse Tester",
        )
        db.session.flush()

        profile = StudentProfile.query.filter_by(user_id=user.id).first()
        if profile is None:
            profile = StudentProfile(user_id=user.id)
            db.session.add(profile)
        profile.campus_id = campus_id
        profile.university_id = university_id
        db.session.commit()
        return user.id


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess["_user_id"] = user_id
        sess["_fresh"] = True


# ── 1. No location -> defaults to General Campus Area ──────
def test_submission_without_location_defaults_to_general_campus_area(app, client):
    with app.app_context():
        campus_id, university_id, gc_id = _make_campus(app)
        uid = _make_user(app, campus_id, university_id)
        _login(client, uid)

        cat = next(iter(pulse_categories.CATEGORIES))
        rv = client.post(
            "/pulse/report/new",
            data={"category": cat, "description": "", "location_id": ""},
            follow_redirects=False,
        )
        assert rv.status_code in (302, 303)

        reports = CampusReport.query.filter_by(campus_id=campus_id).all()
        assert len(reports) == 1
        assert reports[0].location_id == gc_id


# ── 2. Explicit location is preserved ──────────────────────
def test_submission_with_explicit_location_is_unchanged(app, client):
    with app.app_context():
        campus_id, university_id, _ = _make_campus(app)
        uid = _make_user(app, campus_id, university_id)
        _login(client, uid)

        other = create_location(
            campus_id=campus_id, name="Main Library",
            category="library", lat=8.4930, lng=4.6740,
            source="admin", status="approved",
        )
        db.session.commit()

        cat = next(iter(pulse_categories.CATEGORIES))
        rv = client.post(
            "/pulse/report/new",
            data={"category": cat, "description": "", "location_id": other.id},
            follow_redirects=False,
        )
        assert rv.status_code in (302, 303)

        reports = CampusReport.query.filter_by(campus_id=campus_id).all()
        assert len(reports) == 1
        assert reports[0].location_id == other.id


# ── 3. No GCA on campus -> fallback to NULL, no error ─────
def test_submission_without_general_campus_area_falls_back_to_null(app, client):
    with app.app_context():
        campus_id, university_id, _ = _make_campus(app, with_gca=False)
        uid = _make_user(app, campus_id, university_id)
        _login(client, uid)

        cat = next(iter(pulse_categories.CATEGORIES))
        rv = client.post(
            "/pulse/report/new",
            data={"category": cat, "description": "", "location_id": ""},
            follow_redirects=False,
        )
        assert rv.status_code in (302, 303)

        reports = CampusReport.query.filter_by(campus_id=campus_id).all()
        assert len(reports) == 1
        assert reports[0].location_id is None


# ── 4. Campus isolation ────────────────────────────────────
def test_campus_isolation_for_default_assignment(app, client):
    with app.app_context():
        campus_a, uni_a, gc_a = _make_campus(app)
        campus_b, uni_b, gc_b = _make_campus(app)
        uid = _make_user(app, campus_a, uni_a)
        _login(client, uid)

        cat = next(iter(pulse_categories.CATEGORIES))
        rv = client.post(
            "/pulse/report/new",
            data={"category": cat, "description": "", "location_id": ""},
            follow_redirects=False,
        )
        assert rv.status_code in (302, 303)

        report = CampusReport.query.filter_by(campus_id=campus_a).one()
        assert report.location_id == gc_a
        assert report.location_id != gc_b


# ── 5. /map/api/pulse includes the defaulted report (authenticated) ──
def test_api_pulse_includes_report_defaulted_to_general_campus_area(app, client):
    with app.app_context():
        campus_id, university_id, gc_id = _make_campus(app)
        uid = _make_user(app, campus_id, university_id)
        _login(client, uid)

        cat = next(iter(pulse_categories.CATEGORIES))
        rv = client.post(
            "/pulse/report/new",
            data={"category": cat, "description": "", "location_id": ""},
            follow_redirects=False,
        )
        assert rv.status_code in (302, 303)

        new_report = CampusReport.query.filter_by(campus_id=campus_id).one()

        # Isolation: no other reports for this campus.
        prior = (
            CampusReport.query
            .filter(CampusReport.campus_id == campus_id)
            .filter(CampusReport.id != new_report.id)
            .count()
        )
        assert prior == 0, "Test isolation broken: prior reports exist."

        api = client.get("/map/api/pulse")
        assert api.status_code == 200
        data = api.get_json()
        ids = [r["id"] for r in data.get("reports", [])]
        assert new_report.id in ids

        row = next(r for r in data["reports"] if r["id"] == new_report.id)
        assert row["lat"] == pytest.approx(8.4920, abs=1e-6)
        assert row["lng"] == pytest.approx(4.6736, abs=1e-6)


# ── 6. Duplicate GCA -> fallback to NULL (safeguard) ──────
def test_duplicate_general_campus_area_falls_back_to_null(app, client):
    with app.app_context():
        campus_id, university_id, _ = _make_campus(app)
        # Create a second GCA on the same campus.
        create_location(
            campus_id=campus_id, name="General Campus Area",
            category="landmark", lat=8.4921, lng=4.6737,
            source="admin", status="approved",
        )
        db.session.commit()

        uid = _make_user(app, campus_id, university_id)
        _login(client, uid)

        cat = next(iter(pulse_categories.CATEGORIES))
        rv = client.post(
            "/pulse/report/new",
            data={"category": cat, "description": "", "location_id": ""},
            follow_redirects=False,
        )
        assert rv.status_code in (302, 303)

        report = CampusReport.query.filter_by(campus_id=campus_id).one()
        assert report.location_id is None