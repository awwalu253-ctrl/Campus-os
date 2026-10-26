"""Tests for the "Continue without a level" skip path on onboarding step 6.

Covers Phase 3.8B follow-up behaviour:
  1. Skipping (empty level_id) leaves profile.level_id as-is and redirects
     to /home. The student is still considered onboarded.
  2. A valid non-empty level_id saves normally.
  3. Skipping preserves an existing level_id (does not silently clear it).
  4. A bogus non-empty level_id still returns 404 (validation is not
     loosened).

Fixtures commit explicitly (not just flush) because the Flask test
client opens its own session per request — uncommitted fixture data
would be discarded between setup and the POST.
"""
import uuid

import pytest

from app.auth import services as auth_services
from app.extensions import db
from app.models import (
    User, University, Campus, Faculty, Department, Programme, Level,
    StudentProfile,
)


def _login(client, user_id):
    with client.session_transaction() as s:
        s["_user_id"] = user_id
        s["_fresh"] = True


def _make_student(*, university_id, campus_id, faculty_id=None,
                  department_id=None, programme_id=None, level_id=None):
    suffix = uuid.uuid4().hex[:8]
    u = auth_services.create_user(
        email=f"skip-{suffix}@example.com",
        password="testpass1234",
        display_name="Skip Test",
    )
    u.profile = StudentProfile(
        user_id=u.id,
        university_id=university_id,
        campus_id=campus_id,
        faculty_id=faculty_id,
        department_id=department_id,
        programme_id=programme_id,
        level_id=level_id,
    )
    db.session.add(u.profile)
    db.session.commit()
    return u.id


@pytest.fixture
def programme_no_levels(app):
    """A programme with no Level children."""
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]

        uni = University(
            slug=f"nl-uni-{suffix}", name=f"No Level Uni {suffix}",
            short_name="NLU", state="Test", is_active=True,
        )
        db.session.add(uni)
        db.session.commit()

        campus = Campus(
            university_id=uni.id, slug="main", name="Main Campus",
        )
        db.session.add(campus)
        db.session.commit()

        faculty = Faculty(campus_id=campus.id, name="Faculty A", code="FA")
        db.session.add(faculty)
        db.session.commit()

        dept = Department(faculty_id=faculty.id, name="Dept A", code="DA")
        db.session.add(dept)
        db.session.commit()

        prog = Programme(department_id=dept.id, name="Prog A", code="PA")
        db.session.add(prog)
        db.session.commit()

        return {
            "university_id": uni.id,
            "campus_id": campus.id,
            "faculty_id": faculty.id,
            "department_id": dept.id,
            "programme_id": prog.id,
        }


@pytest.fixture
def programme_with_levels(app):
    """A programme with four levels (100-400)."""
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]

        uni = University(
            slug=f"wl-uni-{suffix}", name=f"With Level Uni {suffix}",
            short_name="WLU", state="Test", is_active=True,
        )
        db.session.add(uni)
        db.session.commit()

        campus = Campus(
            university_id=uni.id, slug="main", name="Main Campus",
        )
        db.session.add(campus)
        db.session.commit()

        faculty = Faculty(campus_id=campus.id, name="Faculty B", code="FB")
        db.session.add(faculty)
        db.session.commit()

        dept = Department(faculty_id=faculty.id, name="Dept B", code="DB")
        db.session.add(dept)
        db.session.commit()

        prog = Programme(department_id=dept.id, name="Prog B", code="PB")
        db.session.add(prog)
        db.session.commit()

        level_ids = []
        for rank in (100, 200, 300, 400):
            lvl = Level(
                programme_id=prog.id,
                name=f"{rank} Level",
                rank=rank,
            )
            db.session.add(lvl)
            db.session.commit()
            level_ids.append(lvl.id)

        return {
            "university_id": uni.id,
            "campus_id": campus.id,
            "faculty_id": faculty.id,
            "department_id": dept.id,
            "programme_id": prog.id,
            "level_ids": level_ids,
        }


# ── 1. Skip sets null and redirects home ──────────────────
def test_skip_level_sets_null_and_redirects_home(app, client, programme_no_levels):
    with app.app_context():
        sid = _make_student(
            university_id=programme_no_levels["university_id"],
            campus_id=programme_no_levels["campus_id"],
            faculty_id=programme_no_levels["faculty_id"],
            department_id=programme_no_levels["department_id"],
            programme_id=programme_no_levels["programme_id"],
            # level_id intentionally not passed — null
        )

    _login(client, sid)
    r = client.post("/onboarding/level", data={"level_id": ""})
    assert r.status_code == 302
    # Flask-Login redirect to /home.
    assert r.headers["Location"].endswith("/home")

    with app.app_context():
        u = db.session.get(User, sid)
        assert u.profile.level_id is None
        assert u.profile.programme_id == programme_no_levels["programme_id"]
        # has_onboarded still True because programme_id is set.
        assert u.has_onboarded is True


# ── 2. Valid level saves normally ─────────────────────────
def test_valid_level_id_saves_normally(app, client, programme_with_levels):
    with app.app_context():
        sid = _make_student(
            university_id=programme_with_levels["university_id"],
            campus_id=programme_with_levels["campus_id"],
            faculty_id=programme_with_levels["faculty_id"],
            department_id=programme_with_levels["department_id"],
            programme_id=programme_with_levels["programme_id"],
        )

    target_level_id = programme_with_levels["level_ids"][1]  # 200 Level

    _login(client, sid)
    r = client.post("/onboarding/level", data={"level_id": target_level_id})
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/home")

    with app.app_context():
        u = db.session.get(User, sid)
        assert u.profile.level_id == target_level_id


# ── 3. Skip preserves existing level ──────────────────────
def test_skip_preserves_existing_level(app, client, programme_with_levels):
    """A student who already has a level set, who submits an empty
    level_id, retains their existing level — the skip path never
    silently clears data."""
    existing_level_id = programme_with_levels["level_ids"][0]  # 100 Level

    with app.app_context():
        sid = _make_student(
            university_id=programme_with_levels["university_id"],
            campus_id=programme_with_levels["campus_id"],
            faculty_id=programme_with_levels["faculty_id"],
            department_id=programme_with_levels["department_id"],
            programme_id=programme_with_levels["programme_id"],
            level_id=existing_level_id,
        )

    _login(client, sid)
    r = client.post("/onboarding/level", data={"level_id": ""})
    assert r.status_code == 302

    with app.app_context():
        u = db.session.get(User, sid)
        # Existing level preserved — not cleared to None.
        assert u.profile.level_id == existing_level_id


# ── 4. Invalid non-empty level_id still 404s ──────────────
def test_invalid_level_id_returns_404(app, client, programme_with_levels):
    """A non-empty but invalid level_id must not be treated as a skip.
    Validation on the "has a value" path is unchanged."""
    with app.app_context():
        sid = _make_student(
            university_id=programme_with_levels["university_id"],
            campus_id=programme_with_levels["campus_id"],
            faculty_id=programme_with_levels["faculty_id"],
            department_id=programme_with_levels["department_id"],
            programme_id=programme_with_levels["programme_id"],
        )

    _login(client, sid)
    r = client.post("/onboarding/level", data={"level_id": "not-a-real-level-id"})
    assert r.status_code == 404