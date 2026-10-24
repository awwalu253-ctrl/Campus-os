"""Seed Trinity University's academic hierarchy (faculties, departments, programmes).

Phase 3.8B. Levels are intentionally NOT seeded — see module docstring below.

=== SCOPE ===

Creates for Trinity University (Yaba campus, slug `trinity` / `yaba`):

  - 3 faculties
  - 18 departments
  - 17 programmes
  - 0 levels

The Nursing faculty's four departments are seeded with NO programmes.
Their programme-to-department mapping is not published on any official
source, and inventing one would fabricate academic structure.

=== SOURCE VERIFICATION ===

Primary source (all programmes-to-departments and faculty names):
  https://www.trinityuniversity.edu.ng/discover-the-diverse-programs/

Secondary / cross-check:
  https://www.trinityuniversity.edu.ng/faculties/ — confirms
  "Basic Medical and Applied Sciences" houses six departments and
  nine programs, matching our manifest.

Conflicting sources (documented, resolved in favour of the primary):
  - The Faculties page omits Marketing and Tourism as departments;
    the Discover page lists both. We follow the Discover page.
  - The Management Sciences handbook describes Marketing as a
    programme inside a "Management Sciences" department. We treat it
    as a standalone department per the Discover page.
  - The Nursing faculty vs. department classification is inconsistent
    across the university's own pages. We treat Nursing as a separate
    faculty per the more recent, structured Discover and Faculties
    pages.

Levels are NOT seeded. Only B.Sc Economics, B.Sc Accounting,
B.Sc Business Administration, and B.Sc Marketing have officially
verified 4-year / 100–400 structure. Seeding 4 of 17 would imply the
other 13 have different durations, which is false. Students whose
programme has no levels will see the step-6 empty state (honest).

=== IDEMPOTENCY / SAFETY ===

  - Faculty matched by (campus_id, name). Skip if exists.
  - Department matched by (faculty_id, name). Skip if exists.
  - Programme matched by (department_id, name). Skip if exists.
  - Never overwrites. Never deletes.
  - Aborts before any insert if Trinity or its Yaba campus is missing.
  - Single transaction; rollback on any exception.
"""
import os
import sys

# Allow `python scripts/seed_academic_trinity.py` from the project root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import University, Campus, Faculty, Department, Programme


# Each entry: (faculty_name, [(department_name, [programme_names])])
# See module docstring for source verification and scope notes.
SEED = [
    ("Faculty of Nursing Sciences", [
        ("Medical/Surgical Nursing", []),
        ("Maternal & Child Nursing", []),
        ("Mental Health Nursing", []),
        ("Community Health Nursing", []),
    ]),
    ("Faculty of Basic Medical and Applied Sciences", [
        ("Biological Sciences", [
            "B.Sc Biology",
            "B.Sc Microbiology",
            "B.Sc Biotechnology",
        ]),
        ("Chemical Sciences", [
            "B.Sc Industrial Chemistry",
        ]),
        ("Computer and Information Sciences", [
            "B.Sc Computer Science",
            "B.Sc Information Technology",
        ]),
        ("Medical Laboratory Science", [
            "B.MLS Medical Laboratory Science",
        ]),
        ("Health Information Management", [
            "B.Sc Health Information Management",
        ]),
        ("Physics with Electronics", [
            "B.Sc Physics with Electronics",
        ]),
    ]),
    ("Faculty of Arts, Management, and Social Sciences", [
        ("Accounting", ["B.Sc Accounting"]),
        ("Business Administration", ["B.Sc Business Administration"]),
        ("English and Literary Studies", ["B.A. English and Literary Studies"]),
        ("Economics", ["B.Sc Economics"]),
        ("Mass Communication", ["B.Sc Mass Communication"]),
        ("Political Science", ["B.Sc Political Science"]),
        ("Marketing", ["B.Sc Marketing"]),
        ("Tourism and Hospitality Management", ["B.Sc Tourism and Hospitality Management"]),
    ]),
]


def main():
    app = create_app()
    with app.app_context():
        # ── Resolve Trinity + Yaba campus ───────────────
        university = University.query.filter_by(slug="trinity").first()
        if university is None:
            print(
                "ERROR: Trinity University (slug='trinity') not found. "
                "Run scripts/seed_academic_trinity_tau.py first. Aborting."
            )
            return

        campus = Campus.query.filter_by(
            university_id=university.id,
            slug="yaba",
        ).first()
        if campus is None:
            print(
                "ERROR: Yaba campus (slug='yaba') not found under Trinity. "
                "Run scripts/seed_academic_trinity_tau.py first. Aborting."
            )
            return

        added_fac = 0
        skipped_fac = 0
        added_dept = 0
        skipped_dept = 0
        added_prog = 0
        skipped_prog = 0

        try:
            for faculty_name, dept_specs in SEED:
                faculty = Faculty.query.filter_by(
                    campus_id=campus.id, name=faculty_name,
                ).first()
                if faculty is not None:
                    skipped_fac += 1
                else:
                    faculty = Faculty(campus_id=campus.id, name=faculty_name)
                    db.session.add(faculty)
                    db.session.flush()
                    added_fac += 1

                for dept_name, prog_names in dept_specs:
                    dept = Department.query.filter_by(
                        faculty_id=faculty.id, name=dept_name,
                    ).first()
                    if dept is not None:
                        skipped_dept += 1
                    else:
                        dept = Department(faculty_id=faculty.id, name=dept_name)
                        db.session.add(dept)
                        db.session.flush()
                        added_dept += 1

                    for prog_name in prog_names:
                        prog = Programme.query.filter_by(
                            department_id=dept.id, name=prog_name,
                        ).first()
                        if prog is not None:
                            skipped_prog += 1
                        else:
                            db.session.add(Programme(
                                department_id=dept.id, name=prog_name,
                            ))
                            added_prog += 1

            db.session.commit()
        except Exception:
            db.session.rollback()
            print("Seed failed — transaction rolled back.")
            raise

        print(f"Faculties:  added {added_fac},  skipped {skipped_fac} existing.")
        print(f"Departments: added {added_dept}, skipped {skipped_dept} existing.")
        print(f"Programmes: added {added_prog}, skipped {skipped_prog} existing.")
        print(
            "NOTE: no levels seeded — see module docstring for source "
            "verification notes."
        )


if __name__ == "__main__":
    main()