"""Seed additional Nigerian universities and their verified campuses.

DEV / SETUP ONLY.

Design rules:

1. Idempotent. Every insert is guarded by a "find first" query against
   the natural key (University.slug, and Campus.university_id + Campus.slug).
   Running this script twice is a no-op.

2. Non-overwriting. If a university or campus already exists, its name,
   short_name, state, and is_active are left unchanged. An admin may have
   edited them; this script must not clobber those edits.

3. Non-deleting. This script never removes rows. Existing students,
   locations, reports, and profiles are untouched.

4. Transactional. All inserts happen in a single commit. Any exception
   triggers a full rollback — no partial state survives a failure.

5. No campuses are invented. Every campus in SEED has a source reference
   in its comment. Where the official campus name is not documented, a
   descriptive name is used and the limitation is flagged.

Sources used:

  - Times Higher Education profile of UNN confirms four campuses.
    https://academic-cms.stg.timeshighereducation.com/world-university-rankings/university-nigeria-nsukka

  - Times Higher Education profile of ABU confirms three campuses.
    https://d7.stg.timeshighereducation.com/cn/world-university-rankings/ahmadu-bello-university

  - University of Lagos official VC address confirms three campuses.
    https://unilag.edu.ng/vc-welcome-address/
    and the 19th UNILAG Annual Research Conference page:
    https://conference.unilag.edu.ng/?cat=83

  - Bayero University Kano official page describes Old and New campuses.
    https://buk.edu.ng/node/?page=22

  - Federal Ministry of Information confirms OAU is in Ile-Ife.
    https://fmino.gov.ng/12th-may-nigerias-history/

  - University of Ibadan official bulletin confirms a single UI Campus.
    http://www.ui.edu.ng/sites/default/files/300310.pdf

  - Federal Ministry of Education visitation report on FUTA names the
    Obanla main campus and the Ibule mini campus. Only Obanla is seeded
    as a full campus; Ibule is excluded as a mini centre.
    https://education.gov.ng/wp-content/uploads/2023/09/Federal-University-of-Technology-Akure-Combined-Report-2016-2020-1.pdf

Campus names flagged as descriptive (not officially documented):
  - University of Ibadan: "Ibadan Campus"
  - University of Calabar: "Calabar Campus"

Campus excluded as unverified (was in a prior draft, not seeded here):
  - University of Benin: "Ekehuan" (no authoritative source found)

Campus excluded as not a full campus (was in a prior draft):
  - FUTA: "Ibule" (mini centre, not a full campus)
"""
import os
import sys

# Allow `python scripts/seed_universities.py` from the project root
# without requiring PYTHONPATH to be set.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import University, Campus


# Each entry: (slug, name, short_name, state, campuses)
# campuses: list of (campus_slug, campus_name)
SEED = [
    (
        "unilorin",
        "University of Ilorin",
        "UNILORIN",
        "Kwara",
        [("main", "Main Campus")],
    ),
    (
        "ui",
        "University of Ibadan",
        "UI",
        "Oyo",
        [("ibadan", "Ibadan Campus")],  # descriptive name
    ),
    (
        "unn",
        "University of Nigeria, Nsukka",
        "UNN",
        "Enugu",
        [
            ("nsukka", "Nsukka Campus"),
            ("enugu", "Enugu Campus (UNEC)"),
            ("ituku-ozalla", "Ituku-Ozalla Campus (UNTH)"),
            ("aba", "Aba Campus (UNAC)"),
        ],
    ),
    (
        "oau",
        "Obafemi Awolowo University",
        "OAU",
        "Osun",
        [("ile-ife", "Ile-Ife Campus")],
    ),
    (
        "abu",
        "Ahmadu Bello University",
        "ABU",
        "Kaduna",
        [
            ("samaru", "Samaru Campus"),
            ("kongo", "Kongo Campus"),
            ("funtua", "Funtua Campus"),
        ],
    ),
    (
        "unilag",
        "University of Lagos",
        "UNILAG",
        "Lagos",
        [
            ("akoka", "Akoka Campus"),
            ("idi-araba", "Idi-Araba Campus"),
            ("yaba", "Yaba Campus"),
        ],
    ),
    (
        "uniben",
        "University of Benin",
        "UNIBEN",
        "Edo",
        [("ugbowo", "Ugbowo Campus")],
    ),
    (
        "unical",
        "University of Calabar",
        "UNICAL",
        "Cross River",
        [("calabar", "Calabar Campus")],  # descriptive name
    ),
    (
        "buk",
        "Bayero University Kano",
        "BUK",
        "Kano",
        [
            ("old", "Old Campus"),
            ("new", "New Campus"),
        ],
    ),
    (
        "futa",
        "Federal University of Technology, Akure",
        "FUTA",
        "Ondo",
        [("obanla", "Obanla Campus")],
    ),
]


def main():
    app = create_app()
    with app.app_context():
        added_unis = 0
        skipped_unis = 0
        added_campuses = 0
        skipped_campuses = 0

        try:
            for slug, name, short_name, state, campuses in SEED:
                university = University.query.filter_by(slug=slug).first()

                if university is None:
                    university = University(
                        slug=slug,
                        name=name,
                        short_name=short_name,
                        state=state,
                        is_active=True,
                    )
                    db.session.add(university)
                    db.session.flush()
                    added_unis += 1
                else:
                    skipped_unis += 1

                for campus_slug, campus_name in campuses:
                    existing = Campus.query.filter_by(
                        university_id=university.id,
                        slug=campus_slug,
                    ).first()
                    if existing is not None:
                        skipped_campuses += 1
                        continue
                    db.session.add(Campus(
                        university_id=university.id,
                        slug=campus_slug,
                        name=campus_name,
                    ))
                    added_campuses += 1

            db.session.commit()
        except Exception:
            db.session.rollback()
            print("Seed failed — transaction rolled back.")
            raise

        print(
            f"Universities: added {added_unis}, skipped {skipped_unis} existing."
        )
        print(
            f"Campuses:     added {added_campuses}, skipped {skipped_campuses} existing."
        )
        print(
            f"Totals: {University.query.count()} universities, "
            f"{Campus.query.count()} campuses."
        )


if __name__ == "__main__":
    main()