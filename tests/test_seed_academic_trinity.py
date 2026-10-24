"""Tests for the Trinity University academic hierarchy seed.

Covers Phase 3.8B behaviour:
  1. Correct counts: 3 faculties, 18 departments, 17 programmes.
  2. Correct per-faculty breakdown: 4+6+8 departments, 0+9+8 programmes.
  3. Zero levels are created (deferred to a future phase).
  4. Idempotency: running twice is a no-op.
  5. Preservation: pre-existing faculties with different names are
     left untouched.
  6. Abort behaviour: if Trinity or its Yaba campus is missing, nothing
     is inserted.

The seed's `main()` opens its own app context. Tests replicate the
insert logic inline (same pattern used by all prior seed tests) so
that fixtures control the setup and there is no subprocess machinery.
"""
import uuid

import pytest

from app.extensions import db
from app.models import (
    University, Campus, Faculty, Department, Programme, Level,
)
from scripts.seed_academic_trinity import SEED


def _run_seed():
    """Replicate the seed's insert logic inline against the current DB state.

    Assumes `trinity` university and `yaba` campus already exist
    (created by the fixture below).
    """
    university = University.query.filter_by(slug="trinity").first()
    if university is None:
        return  # abort case (test asserts no rows were created)
    campus = Campus.query.filter_by(
        university_id=university.id, slug="yaba",
    ).first()
    if campus is None:
        return

    for faculty_name, dept_specs in SEED:
        faculty = Faculty.query.filter_by(
            campus_id=campus.id, name=faculty_name,
        ).first()
        if faculty is None:
            faculty = Faculty(campus_id=campus.id, name=faculty_name)
            db.session.add(faculty)
            db.session.flush()

        for dept_name, prog_names in dept_specs:
            dept = Department.query.filter_by(
                faculty_id=faculty.id, name=dept_name,
            ).first()
            if dept is None:
                dept = Department(faculty_id=faculty.id, name=dept_name)
                db.session.add(dept)
                db.session.flush()

            for prog_name in prog_names:
                existing = Programme.query.filter_by(
                    department_id=dept.id, name=prog_name,
                ).first()
                if existing is None:
                    db.session.add(Programme(
                        department_id=dept.id, name=prog_name,
                    ))
    db.session.commit()


@pytest.fixture
def trinity(app):
    """Trinity University and its Yaba campus, no academic hierarchy."""
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        uni = University(
            slug="trinity",
            name=f"Trinity University, Yaba {suffix}",
            short_name="Trinity",
            state="Lagos",
            is_active=True,
        )
        db.session.add(uni)
        db.session.commit()

        campus = Campus(
            university_id=uni.id, slug="yaba", name="Yaba Campus",
        )
        db.session.add(campus)
        db.session.commit()

        return {
            "university_id": uni.id,
            "campus_id": campus.id,
        }


# ── 1. Faculty count ──────────────────────────────────────
def test_seed_creates_three_faculties(app, trinity):
    with app.app_context():
        _run_seed()

        faculties = Faculty.query.filter_by(campus_id=trinity["campus_id"]).all()
        assert len(faculties) == 3

        names = sorted(f.name for f in faculties)
        assert names == [
            "Faculty of Arts, Management, and Social Sciences",
            "Faculty of Basic Medical and Applied Sciences",
            "Faculty of Nursing Sciences",
        ]


# ── 2. Department count + breakdown ───────────────────────
def test_seed_creates_eighteen_departments(app, trinity):
    with app.app_context():
        _run_seed()

        # Total across Trinity's campus.
        total = (
            Department.query
            .join(Faculty, Department.faculty_id == Faculty.id)
            .filter(Faculty.campus_id == trinity["campus_id"])
            .count()
        )
        assert total == 18

        # Per-faculty breakdown.
        nursing = Faculty.query.filter_by(
            campus_id=trinity["campus_id"],
            name="Faculty of Nursing Sciences",
        ).one()
        assert Department.query.filter_by(faculty_id=nursing.id).count() == 4

        basic = Faculty.query.filter_by(
            campus_id=trinity["campus_id"],
            name="Faculty of Basic Medical and Applied Sciences",
        ).one()
        assert Department.query.filter_by(faculty_id=basic.id).count() == 6

        arts = Faculty.query.filter_by(
            campus_id=trinity["campus_id"],
            name="Faculty of Arts, Management, and Social Sciences",
        ).one()
        assert Department.query.filter_by(faculty_id=arts.id).count() == 8


# ── 3. Programme count + breakdown ────────────────────────
def test_seed_creates_seventeen_programmes(app, trinity):
    with app.app_context():
        _run_seed()

        total = (
            Programme.query
            .join(Department, Programme.department_id == Department.id)
            .join(Faculty, Department.faculty_id == Faculty.id)
            .filter(Faculty.campus_id == trinity["campus_id"])
            .count()
        )
        assert total == 17

        # Nursing has zero programmes.
        nursing = Faculty.query.filter_by(
            campus_id=trinity["campus_id"],
            name="Faculty of Nursing Sciences",
        ).one()
        nursing_progs = (
            Programme.query
            .join(Department, Programme.department_id == Department.id)
            .filter(Department.faculty_id == nursing.id)
            .count()
        )
        assert nursing_progs == 0

        # Basic Medical has 9 programmes.
        basic = Faculty.query.filter_by(
            campus_id=trinity["campus_id"],
            name="Faculty of Basic Medical and Applied Sciences",
        ).one()
        basic_progs = (
            Programme.query
            .join(Department, Programme.department_id == Department.id)
            .filter(Department.faculty_id == basic.id)
            .count()
        )
        assert basic_progs == 9

        # Arts has 8 programmes.
        arts = Faculty.query.filter_by(
            campus_id=trinity["campus_id"],
            name="Faculty of Arts, Management, and Social Sciences",
        ).one()
        arts_progs = (
            Programme.query
            .join(Department, Programme.department_id == Department.id)
            .filter(Department.faculty_id == arts.id)
            .count()
        )
        assert arts_progs == 8


# ── 4. No levels ──────────────────────────────────────────
def test_seed_creates_no_levels(app, trinity):
    with app.app_context():
        _run_seed()

        # Not a single level exists in the DB after the Trinity seed.
        assert Level.query.count() == 0


# ── 5. Idempotency ────────────────────────────────────────
def test_seed_is_idempotent(app, trinity):
    with app.app_context():
        _run_seed()
        assert Faculty.query.filter_by(campus_id=trinity["campus_id"]).count() == 3

        _run_seed()  # second run

        assert Faculty.query.filter_by(campus_id=trinity["campus_id"]).count() == 3
        assert (
            Department.query
            .join(Faculty, Department.faculty_id == Faculty.id)
            .filter(Faculty.campus_id == trinity["campus_id"])
            .count()
        ) == 18
        assert (
            Programme.query
            .join(Department, Programme.department_id == Department.id)
            .join(Faculty, Department.faculty_id == Faculty.id)
            .filter(Faculty.campus_id == trinity["campus_id"])
            .count()
        ) == 17


# ── 6. Preservation of pre-existing faculties ─────────────
def test_seed_preserves_existing_faculty(app, trinity):
    """Pre-create a faculty with a name not in SEED; verify the seed
    leaves it alone and does not create a duplicate under the same name."""
    with app.app_context():
        other = Faculty(
            campus_id=trinity["campus_id"],
            name="Faculty of Pre-existing Studies",
        )
        db.session.add(other)
        db.session.commit()

        _run_seed()

        # Still exactly 4 faculties: 3 from seed + 1 pre-existing.
        assert (
            Faculty.query.filter_by(campus_id=trinity["campus_id"]).count()
        ) == 4

        # Pre-existing faculty unchanged.
        stored = Faculty.query.filter_by(
            campus_id=trinity["campus_id"],
            name="Faculty of Pre-existing Studies",
        ).one()
        assert stored.name == "Faculty of Pre-existing Studies"
        # And it has no departments (seed didn't try to fill it).
        assert Department.query.filter_by(faculty_id=stored.id).count() == 0


# ── 7. Abort if Trinity missing ───────────────────────────
def test_seed_aborts_if_trinity_missing(app):
    """With no Trinity in the DB, running the seed should insert nothing."""
    with app.app_context():
        assert University.query.filter_by(slug="trinity").first() is None

        _run_seed()  # should return early — no crash, no inserts

        assert Faculty.query.count() == 0
        assert Department.query.count() == 0
        assert Programme.query.count() == 0