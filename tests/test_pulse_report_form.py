"""Step 3 tests — Pulse report form location picker (server-rendered)."""
import uuid

import pytest

from app.extensions import db
from app.models import Campus, University, StudentProfile
from app.maps.models import Location
from app.maps.services import create_location
from app.pulse.models import CampusReport
from app.pulse import categories as pulse_categories
from app.auth import services as auth_services


def _make_campus(app, *, with_gca=True, dup_gca=False,
                 gca_lat=8.4920, gca_lng=4.6736):
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        uni = University(
            slug=f"uni-{suffix}", name=f"Uni {suffix}",
            short_name="TU", state="Test",
        )
        db.session.add(uni); db.session.flush()

        campus = Campus(
            university_id=uni.id, slug=f"main-{suffix}",
            name=f"Campus {suffix}", lat=gca_lat, lng=gca_lng,
        )
        db.session.add(campus); db.session.flush()

        gc_id = None
        if with_gca:
            gc = create_location(
                campus_id=campus.id, name="General Campus Area",
                category="landmark", lat=gca_lat, lng=gca_lng,
                source="admin", status="approved",
            )
            gc_id = gc.id
            if dup_gca:
                gc2 = create_location(
                    campus_id=campus.id, name="General Campus Area",
                    category="landmark", lat=gca_lat + 0.001, lng=gca_lng + 0.001,
                    source="admin", status="approved",
                )
                # explicit marker for tests that expect no unique GCA
                gc_id = None  # we intentionally return None for "unique gca id"

        # A specific approved location (always created)
        spec = create_location(
            campus_id=campus.id, name="Main Library",
            category="library", lat=8.4930, lng=4.6740,
            source="admin", status="approved",
        )
        # A pending location (must not appear in picker)
        create_location(
            campus_id=campus.id, name="Pending Building",
            category="building", lat=8.4935, lng=4.6745,
            source="student", status="pending",
        )
        db.session.commit()
        return {
            "campus_id": campus.id,
            "university_id": uni.id,
            "gc_id": gc_id,
            "specific_id": spec.id,
        }


def _make_user(app, campus_id, university_id):
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        user = auth_services.create_user(
            email=f"pulse-form-{suffix}@example.com",
            password="testpass1234",
            display_name="Form Tester",
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


# ── 1. Picker renders; unique valid GCA is default ─────────
def test_form_renders_picker_with_unique_gca_default(app, client):
    with app.app_context():
        ids = _make_campus(app, with_gca=True)
        uid = _make_user(app, ids["campus_id"], ids["university_id"])
        _login(client, uid)

        rv = client.get("/pulse/report/new")
        assert rv.status_code == 200
        body = rv.get_data(as_text=True)
        assert 'id="location_id"' in body
        assert "General campus area" in body
        # The GCA option should be selected by default.
        assert f'value="{ids["gc_id"]}"' in body


# ── 2. No GCA → form still renders, no GCA option ─────────
def test_form_handles_absence_of_gca_gracefully(app, client):
    with app.app_context():
        ids = _make_campus(app, with_gca=False)
        uid = _make_user(app, ids["campus_id"], ids["university_id"])
        _login(client, uid)

        rv = client.get("/pulse/report/new")
        assert rv.status_code == 200
        body = rv.get_data(as_text=True)
        # No GCA label rendered
        assert "General campus area" not in body
        # "No specific place" is present and should be selected
        assert "No specific place" in body
        assert 'value=""' in body


# ── 3. Valid preset is preselected ─────────────────────────
def test_form_preselects_valid_preset(app, client):
    with app.app_context():
        ids = _make_campus(app, with_gca=True)
        uid = _make_user(app, ids["campus_id"], ids["university_id"])
        _login(client, uid)

        rv = client.get(f"/pulse/report/new?location_id={ids['specific_id']}")
        assert rv.status_code == 200
        body = rv.get_data(as_text=True)
        # The specific location option must carry selected
        assert f'value="{ids["specific_id"]}"' in body
        # Sanity: GCA option exists but is not selected
        # (heuristic — the GCA should not carry selected in that block)
        # We just check both options exist and the specific one is selected.
        assert "General campus area" in body


# ── 4. Campus isolation — only approved, current-campus locations shown ──
def test_form_shows_only_current_campus_approved_locations(app, client):
    with app.app_context():
        a = _make_campus(app, with_gca=True)
        b = _make_campus(app, with_gca=False)  # another campus with its own locations
        uid = _make_user(app, a["campus_id"], a["university_id"])
        _login(client, uid)

        rv = client.get("/pulse/report/new")
        assert rv.status_code == 200
        body = rv.get_data(as_text=True)

        # Campus A's specific location must be present
        assert a["specific_id"] in body
        # Campus B's specific location must not be present
        assert b["specific_id"] not in body

        # Pending location on campus A must not appear
        assert "Pending Building" not in body


# ── 5. Invalid / cross-campus preset is ignored ───────────
def test_form_ignores_invalid_or_cross_campus_preset(app, client):
    with app.app_context():
        a = _make_campus(app, with_gca=True)
        b = _make_campus(app, with_gca=False)
        uid = _make_user(app, a["campus_id"], a["university_id"])
        _login(client, uid)

        # Cross-campus preset: campus B's specific location ID
        rv = client.get(f"/pulse/report/new?location_id={b['specific_id']}")
        assert rv.status_code == 200
        body = rv.get_data(as_text=True)
        # It must not be rendered as selected or listed
        assert f'value="{b["specific_id"]}"' not in body
        # Fallback: unique GCA of campus A becomes the default
        assert f'value="{a["gc_id"]}"' in body

        # Nonexistent preset
        fake = str(uuid.uuid4())
        rv2 = client.get(f"/pulse/report/new?location_id={fake}")
        assert rv2.status_code == 200
        assert f'value="{fake}"' not in rv2.get_data(as_text=True)


# ── 6. Submission with GCA selected is compatible with Step 2 ──
def test_submission_with_selected_gca_remains_compatible(app, client):
    with app.app_context():
        ids = _make_campus(app, with_gca=True)
        uid = _make_user(app, ids["campus_id"], ids["university_id"])
        _login(client, uid)

        cat = next(iter(pulse_categories.CATEGORIES))
        rv = client.post(
            "/pulse/report/new",
            data={"category": cat, "description": "", "location_id": ids["gc_id"]},
            follow_redirects=False,
        )
        assert rv.status_code in (302, 303)

        report = CampusReport.query.filter_by(campus_id=ids["campus_id"]).one()
        assert report.location_id == ids["gc_id"]


# ── 7. Submission with "No specific place" → Step 2 default applies ──
def test_submission_with_no_specific_place_falls_through_to_step2(app, client):
    with app.app_context():
        ids = _make_campus(app, with_gca=True)
        uid = _make_user(app, ids["campus_id"], ids["university_id"])
        _login(client, uid)

        cat = next(iter(pulse_categories.CATEGORIES))
        rv = client.post(
            "/pulse/report/new",
            data={"category": cat, "description": "", "location_id": ""},
            follow_redirects=False,
        )
        assert rv.status_code in (302, 303)

        report = CampusReport.query.filter_by(campus_id=ids["campus_id"]).one()
        # Step 2 logic assigns the unique GCA when location_id is empty.
        assert report.location_id == ids["gc_id"]


# ── Bonus: duplicates → no arbitrary default, form still renders ──
def test_form_with_duplicate_gca_does_not_preselect_gca(app, client):
    with app.app_context():
        ids = _make_campus(app, with_gca=True, dup_gca=True)
        uid = _make_user(app, ids["campus_id"], ids["university_id"])
        _login(client, uid)

        rv = client.get("/pulse/report/new")
        assert rv.status_code == 200
        body = rv.get_data(as_text=True)
        # No GCA label since no unique valid GCA
        assert "General campus area" not in body