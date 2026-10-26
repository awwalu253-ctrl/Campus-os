"""Tests for the empty-state branches on onboarding steps 4, 5, and 6.

Covers:
  - Steps 4, 5, 6 show honest empty states when the parent record has
    no children.
  - Steps 4, 5, 6 still show the normal form when the parent record
    has children (regression check).

Each test creates exactly one user and makes exactly one request.
Multi-step tests (using `_login` to switch users between requests) were
avoided because Flask-Login's session-based user switching did not
reliably update `current_user` between test-client requests when a
previous request had already cached user state.
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
                  department_id=None, programme_id=None):
    """Create a student and attach the given hierarchy ids to their profile."""
    suffix = uuid.uuid4().hex[:8]
    u = auth_services.create_user(
        email=f"onboard-{suffix}@example.com",
        password="testpass1234",
        display_name="Onboarding Test",
    )
    u.profile = StudentProfile(
        user_id=u.id,
        university_id=university_id,
        campus_id=campus_id,
        faculty_id=faculty_id,
        department_id=department_id,
        programme_id=programme_id,
    )
    db.session.add(u.profile)
    db.session.commit()
    return u.id


# ── Fixtures ─────────────────────────────────────────────
@pytest.fixture
def base_university_and_campus(app):
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        uni = University(
            slug=f"base-{suffix}", name=f"Base Uni {suffix}",
            short_name="BU", state="Test", is_active=True,
        )
        db.session.add(uni)
        db.session.commit()

        campus = Campus(
            university_id=uni.id, slug="main", name="Main Campus",
        )
        db.session.add(campus)
        db.session.commit()

        return {
            "university_id": uni.id,
            "campus_id": campus.id,
        }


@pytest.fixture
def faculty_with_no_departments(app, base_university_and_campus):
    """Faculty with no department children → step 4 empty state."""
    with app.app_context():
        faculty = Faculty(
            campus_id=base_university_and_campus["campus_id"],
            name="Empty Faculty", code="EF",
        )
        db.session.add(faculty)
        db.session.commit()
        return {
            **base_university_and_campus,
            "faculty_id": faculty.id,
        }


@pytest.fixture
def department_with_no_programmes(app, faculty_with_no_departments):
    """Faculty with one department, and that department has no programmes
    → step 5 empty state."""
    with app.app_context():
        dept = Department(
            faculty_id=faculty_with_no_departments["faculty_id"],
            name="Empty Dept", code="ED",
        )
        db.session.add(dept)
        db.session.commit()
        return {
            **faculty_with_no_departments,
            "department_id": dept.id,
        }


@pytest.fixture
def programme_with_no_levels(app, department_with_no_programmes):
    """Department with one programme, and that programme has no levels
    → step 6 empty state."""
    with app.app_context():
        prog = Programme(
            department_id=department_with_no_programmes["department_id"],
            name="Empty Programme", code="EP",
        )
        db.session.add(prog)
        db.session.commit()
        return {
            **department_with_no_programmes,
            "programme_id": prog.id,
        }


@pytest.fixture
def faculty_with_departments(app, base_university_and_campus):
    """Faculty with at least one department → step 4 renders form."""
    with app.app_context():
        faculty = Faculty(
            campus_id=base_university_and_campus["campus_id"],
            name="Faculty With Depts", code="FWD",
        )
        db.session.add(faculty)
        db.session.commit()

        dept = Department(
            faculty_id=faculty.id, name="Dept 1", code="D1",
        )
        db.session.add(dept)
        db.session.commit()

        return {
            **base_university_and_campus,
            "faculty_id": faculty.id,
            "department_id": dept.id,
        }


@pytest.fixture
def department_with_programmes(app, faculty_with_departments):
    """Department with at least one programme → step 5 renders form."""
    with app.app_context():
        prog = Programme(
            department_id=faculty_with_departments["department_id"],
            name="Prog 1", code="P1",
        )
        db.session.add(prog)
        db.session.commit()

        return {
            **faculty_with_departments,
            "programme_id": prog.id,
        }


@pytest.fixture
def programme_with_levels(app, department_with_programmes):
    """Programme with four levels → step 6 renders form."""
    with app.app_context():
        for rank in (100, 200, 300, 400):
            db.session.add(Level(
                programme_id=department_with_programmes["programme_id"],
                name=f"{rank} Level",
                rank=rank,
            ))
        db.session.commit()

        return {
            **department_with_programmes,
        }


# ── Empty state tests ────────────────────────────────────
def test_step4_shows_empty_state_when_faculty_has_no_departments(
    app, client, faculty_with_no_departments
):
    with app.app_context():
        sid = _make_student(
            university_id=faculty_with_no_departments["university_id"],
            campus_id=faculty_with_no_departments["campus_id"],
            faculty_id=faculty_with_no_departments["faculty_id"],
        )

    _login(client, sid)
    r = client.get("/onboarding/department")
    assert r.status_code == 200

    body = r.data
    assert b"Department information not yet available" in body
    assert b"Back to faculties" in body
    assert b'name="department_id"' not in body


def test_step5_shows_empty_state_when_department_has_no_programmes(
    app, client, department_with_no_programmes
):
    with app.app_context():
        sid = _make_student(
            university_id=department_with_no_programmes["university_id"],
            campus_id=department_with_no_programmes["campus_id"],
            faculty_id=department_with_no_programmes["faculty_id"],
            department_id=department_with_no_programmes["department_id"],
        )

    _login(client, sid)
    r = client.get("/onboarding/programme")
    assert r.status_code == 200

    body = r.data
    assert b"Programme information not yet available" in body
    assert b"Back to departments" in body
    assert b'name="programme_id"' not in body


def test_step6_shows_empty_state_when_programme_has_no_levels(
    app, client, programme_with_no_levels
):
    with app.app_context():
        sid = _make_student(
            university_id=programme_with_no_levels["university_id"],
            campus_id=programme_with_no_levels["campus_id"],
            faculty_id=programme_with_no_levels["faculty_id"],
            department_id=programme_with_no_levels["department_id"],
            programme_id=programme_with_no_levels["programme_id"],
        )

    _login(client, sid)
    r = client.get("/onboarding/level")
    assert r.status_code == 200

    body = r.data
    assert b"Level information not yet available" in body
    assert b"Back to programmes" in body
    assert b'type="radio" name="level_id"' not in body


# ── Happy path tests (one per step) ───────────────────────
def test_step4_renders_department_form_when_faculty_has_departments(
    app, client, faculty_with_departments
):
    with app.app_context():
        sid = _make_student(
            university_id=faculty_with_departments["university_id"],
            campus_id=faculty_with_departments["campus_id"],
            faculty_id=faculty_with_departments["faculty_id"],
        )

    _login(client, sid)
    r = client.get("/onboarding/department")
    assert r.status_code == 200

    body = r.data
    assert b'name="department_id"' in body
    assert b"Department information not yet available" not in body


def test_step5_renders_programme_form_when_department_has_programmes(
    app, client, department_with_programmes
):
    with app.app_context():
        sid = _make_student(
            university_id=department_with_programmes["university_id"],
            campus_id=department_with_programmes["campus_id"],
            faculty_id=department_with_programmes["faculty_id"],
            department_id=department_with_programmes["department_id"],
        )

    _login(client, sid)
    r = client.get("/onboarding/programme")
    assert r.status_code == 200

    body = r.data
    assert b'name="programme_id"' in body
    assert b"Programme information not yet available" not in body


def test_step6_renders_level_form_when_programme_has_levels(
    app, client, programme_with_levels
):
    with app.app_context():
        sid = _make_student(
            university_id=programme_with_levels["university_id"],
            campus_id=programme_with_levels["campus_id"],
            faculty_id=programme_with_levels["faculty_id"],
            department_id=programme_with_levels["department_id"],
            programme_id=programme_with_levels["programme_id"],
        )

    _login(client, sid)
    r = client.get("/onboarding/level")
    assert r.status_code == 200

    body = r.data
    assert b'name="level_id"' in body
    assert b"Level information not yet available" not in body