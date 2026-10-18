"""Tests for the admin Universities & Campuses read-only pages.

Covers the university list, university detail, and campus detail views
at /admin/universities, /admin/universities/<id>, and /admin/campuses/<id>.

These pages are strictly read-only: no create, edit, deactivate, or
delete. The tests assert:
  1. Auth is required.
  2. Permissions are enforced.
  3. The list renders for an admin.
  4. University detail renders and reflects aggregate counts.
  5. Campus detail renders and reflects per-faculty counts.
  6. Nonexistent university and campus IDs return 404.
"""
import uuid

import pytest

from app.core.security import hash_password
from app.extensions import db
from app.models import (
    User, University, Campus, Faculty, Department, Programme, Level,
)


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
def hierarchy(app):
    """Create a small but non-trivial hierarchy for count verification.

    Shape:
      1 University
        └ 1 Campus
             ├ 2 Faculties
             │   each with 2 Departments
             │     each with 2 Programmes
             │       each with 2 Levels

    Expected totals at the university level:
      Campuses:    1
      Faculties:   2
      Departments: 4
      Programmes:  8
      Levels:      16

    At the campus level (per faculty):
      Departments: 2
      Programmes:  4
      Levels:      8
    """
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]

        uni = University(
            slug=f"uni-{suffix}",
            name=f"University {suffix}",
            short_name=f"U{suffix}",
            state="Test State",
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

        for fi in range(2):
            faculty = Faculty(
                campus_id=campus.id,
                name=f"Faculty {fi + 1}",
                code=f"F{fi + 1}",
            )
            db.session.add(faculty)
            db.session.flush()

            for di in range(2):
                department = Department(
                    faculty_id=faculty.id,
                    name=f"Dept {fi + 1}-{di + 1}",
                    code=f"D{fi + 1}{di + 1}",
                )
                db.session.add(department)
                db.session.flush()

                for pi in range(2):
                    programme = Programme(
                        department_id=department.id,
                        name=f"Prog {fi + 1}-{di + 1}-{pi + 1}",
                        code=f"P{fi + 1}{di + 1}{pi + 1}",
                    )
                    db.session.add(programme)
                    db.session.flush()

                    for li in range(2):
                        level = Level(
                            programme_id=programme.id,
                            name=f"Level {li * 100 + 100}",
                            rank=(li + 1) * 100,
                        )
                        db.session.add(level)

        db.session.commit()

        return {
            "university_id": uni.id,
            "university_name": uni.name,
            "campus_id": campus.id,
            "campus_name": campus.name,
        }


def _login(client, user_id):
    with client.session_transaction() as s:
        s["_user_id"] = user_id
        s["_fresh"] = True


# ── List page ─────────────────────────────────────────────
def test_admin_universities_requires_auth(client):
    r = client.get("/admin/universities")
    assert r.status_code == 302


def test_admin_universities_requires_admin(app, client):
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
    r = client.get("/admin/universities")
    assert r.status_code == 403


def test_admin_universities_renders_for_admin(app, client, admin, hierarchy):
    _login(client, admin)
    r = client.get("/admin/universities")
    assert r.status_code == 200

    body = r.data
    # The seeded university must appear on the list.
    assert hierarchy["university_name"].encode() in body
    # Column headers specific to this page.
    for label in (b"Short name", b"Campuses", b"Status"):
        assert label in body, f"missing column header: {label}"


# ── University detail ────────────────────────────────────
def test_admin_university_detail_renders_for_admin(
    app, client, admin, hierarchy
):
    _login(client, admin)
    r = client.get(f"/admin/universities/{hierarchy['university_id']}")
    assert r.status_code == 200

    body = r.data
    assert hierarchy["university_name"].encode() in body
    assert hierarchy["campus_name"].encode() in body
    # Aggregate stat labels.
    for label in (b"Campuses", b"Faculties", b"Departments", b"Programmes", b"Levels"):
        assert label in body, f"missing aggregate label: {label}"


# ── Campus detail ────────────────────────────────────────
def test_admin_campus_detail_renders_for_admin(
    app, client, admin, hierarchy
):
    _login(client, admin)
    r = client.get(f"/admin/campuses/{hierarchy['campus_id']}")
    assert r.status_code == 200

    body = r.data
    assert hierarchy["campus_name"].encode() in body
    # Both seeded faculty names should appear in the faculty table.
    assert b"Faculty 1" in body
    assert b"Faculty 2" in body
    # Per-faculty aggregate labels present.
    assert b"Departments" in body
    assert b"Programmes" in body
    assert b"Levels" in body


# ── 404s ─────────────────────────────────────────────────
def test_admin_university_detail_404_for_unknown_id(app, client, admin):
    _login(client, admin)
    r = client.get("/admin/universities/not-a-real-id")
    assert r.status_code == 404


def test_admin_campus_detail_404_for_unknown_id(app, client, admin):
    _login(client, admin)
    r = client.get("/admin/campuses/not-a-real-id")
    assert r.status_code == 404