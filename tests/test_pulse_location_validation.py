"""Step 4 tests — Pulse POST location validation (cross-campus & approval)."""
import uuid

import pytest

from app.extensions import db
from app.models import Campus, University, StudentProfile
from app.maps.models import Location
from app.maps.services import create_location
from app.pulse.models import CampusReport
from app.pulse import categories as pulse_categories
from app.auth import services as auth_services


def _make_campus(app, *, with_gca=True, dup_gca=False):
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        uni = University(
            slug=f"uni-{suffix}", name=f"Uni {suffix}",
            short_name="TU", state="Test",
        )
        db.session.add(uni); db.session.flush()

        campus = Campus(
            university_id=uni.id, slug=f"main-{suffix}",
            name=f"Campus {suffix}", lat=8.4920, lng=4.6736,
        )
        db.session.add(campus); db.session.flush()

        gc_id = None
        if with_gca:
            gc = create_location(
                campus_id=campus.id, name="General Campus Area",
                category="landmark", lat=8.4920, lng=4.6736,
                source="admin", status="approved",
            )
            gc_id = gc.id
            if dup_gca:
                create_location(
                    campus_id=campus.id, name="General Campus Area",
                    category="landmark", lat=8.4921, lng=4.6737,
                    source="admin", status="approved",
                )
                gc_id = None

        approved = create_location(
            campus_id=campus.id, name="Main Library",
            category="library", lat=8.4930, lng=4.6740,
            source="admin", status="approved",
        )
        pending = create_location(
            campus_id=campus.id, name="Pending Lab",
            category="lab", lat=8.4935, lng=4.6745,
            source="student", status="pending",
        )
        rejected = create_location(
            campus_id=campus.id, name="Rejected Hall",
            category="building", lat=8.4940, lng=4.6750,
            source="student", status="rejected",
        )
        db.session.commit()
        return {
            "campus_id": campus.id,
            "university_id": uni.id,
            "gc_id": gc_id,
            "approved_id": approved.id,
            "pending_id": pending.id,
            "rejected_id": rejected.id,
        }


def _make_user(app, campus_id, university_id):
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        user = auth_services.create_user(
            email=f"pulse-val-{suffix}@example.com",
            password="testpass1234",
            display_name="Validation Tester",
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


def _cat():
    return next(iter(pulse_categories.CATEGORIES))


def _count_reports(campus_id):
    return CampusReport.query.filter_by(campus_id=campus_id).count()


# ── 1. Same-campus approved location is accepted ─────────
def test_same_campus_approved_location_accepted(app, client):
    with app.app_context():
        ids = _make_campus(app)
        uid = _make_user(app, ids["campus_id"], ids["university_id"])
        _login(client, uid)

        rv = client.post(
            "/pulse/report/new",
            data={"category": _cat(), "description": "",
                  "location_id": ids["approved_id"]},
            follow_redirects=False,
        )
        assert rv.status_code in (302, 303)
        report = CampusReport.query.filter_by(campus_id=ids["campus_id"]).one()
        assert report.location_id == ids["approved_id"]


# ── 2. Cross-campus location is rejected ──────────────────
def test_cross_campus_location_rejected(app, client):
    with app.app_context():
        a = _make_campus(app)
        b = _make_campus(app)
        uid = _make_user(app, a["campus_id"], a["university_id"])
        _login(client, uid)

        cat = _cat()
        desc = "my test description"
        rv = client.post(
            "/pulse/report/new",
            data={"category": cat, "description": desc,
                  "location_id": b["approved_id"]},
            follow_redirects=False,
        )
        assert rv.status_code == 200
        assert _count_reports(a["campus_id"]) == 0
        assert _count_reports(b["campus_id"]) == 0

        body = rv.get_data(as_text=True)
        assert f'value="{cat}"' in body
        assert f'value="{desc}"' in body


# ── 3. Nonexistent location is rejected ───────────────────
def test_nonexistent_location_rejected(app, client):
    with app.app_context():
        ids = _make_campus(app)
        uid = _make_user(app, ids["campus_id"], ids["university_id"])
        _login(client, uid)

        fake = str(uuid.uuid4())
        cat = _cat()
        desc = "ghost location attempt"
        rv = client.post(
            "/pulse/report/new",
            data={"category": cat, "description": desc, "location_id": fake},
            follow_redirects=False,
        )
        assert rv.status_code == 200
        assert _count_reports(ids["campus_id"]) == 0

        body = rv.get_data(as_text=True)
        assert f'value="{cat}"' in body
        assert f'value="{desc}"' in body


# ── 4. Pending location is rejected ───────────────────────
def test_pending_location_rejected(app, client):
    with app.app_context():
        ids = _make_campus(app)
        uid = _make_user(app, ids["campus_id"], ids["university_id"])
        _login(client, uid)

        rv = client.post(
            "/pulse/report/new",
            data={"category": _cat(), "description": "",
                  "location_id": ids["pending_id"]},
            follow_redirects=False,
        )
        assert rv.status_code == 200
        assert _count_reports(ids["campus_id"]) == 0


# ── 5. Rejected location is rejected ──────────────────────
def test_rejected_location_rejected(app, client):
    with app.app_context():
        ids = _make_campus(app)
        uid = _make_user(app, ids["campus_id"], ids["university_id"])
        _login(client, uid)

        rv = client.post(
            "/pulse/report/new",
            data={"category": _cat(), "description": "",
                  "location_id": ids["rejected_id"]},
            follow_redirects=False,
        )
        assert rv.status_code == 200
        assert _count_reports(ids["campus_id"]) == 0


# ── 6. Empty location still uses Step 2 GCA fallback ──────
def test_empty_location_uses_step2_gca_fallback(app, client):
    with app.app_context():
        ids = _make_campus(app)
        uid = _make_user(app, ids["campus_id"], ids["university_id"])
        _login(client, uid)

        rv = client.post(
            "/pulse/report/new",
            data={"category": _cat(), "description": "", "location_id": ""},
            follow_redirects=False,
        )
        assert rv.status_code in (302, 303)
        report = CampusReport.query.filter_by(campus_id=ids["campus_id"]).one()
        assert report.location_id == ids["gc_id"]


# ── 7. Explicit valid GCA is accepted ─────────────────────
def test_explicit_gca_accepted(app, client):
    with app.app_context():
        ids = _make_campus(app)
        uid = _make_user(app, ids["campus_id"], ids["university_id"])
        _login(client, uid)

        rv = client.post(
            "/pulse/report/new",
            data={"category": _cat(), "description": "",
                  "location_id": ids["gc_id"]},
            follow_redirects=False,
        )
        assert rv.status_code in (302, 303)
        report = CampusReport.query.filter_by(campus_id=ids["campus_id"]).one()
        assert report.location_id == ids["gc_id"]


# ── 8. Duplicate GCA + empty selection → NULL fallback ────
def test_duplicate_gca_empty_selection_falls_back_to_null(app, client):
    with app.app_context():
        ids = _make_campus(app, dup_gca=True)
        uid = _make_user(app, ids["campus_id"], ids["university_id"])
        _login(client, uid)

        rv = client.post(
            "/pulse/report/new",
            data={"category": _cat(), "description": "", "location_id": ""},
            follow_redirects=False,
        )
        assert rv.status_code in (302, 303)
        report = CampusReport.query.filter_by(campus_id=ids["campus_id"]).one()
        assert report.location_id is None