"""Seed campus center coordinates for the two pilot campuses.

DEV / PILOT ONLY.

Sets Campus.lat / Campus.lng for campuses whose coordinates have been
verified to the level required for map centering. Currently:

  - UNILORIN 'main'  : 8.4826, 4.6736
                       Same values as the hardcoded map.js fallback.
                       The 39 seeded UNILORIN locations all sit within
                       a small radius of this point; using it as the
                       map center is proven safe.

  - UNILAG   'akoka' : 6.51821, 3.39556
                       APPROXIMATE. Third-party map data (OpenStreetMap),
                       not an official UNILAG coordinate. See Phase 3.2
                       for the full caveat. Adequate for the pilot.

The other 16 campuses have no verified coordinates. They remain NULL
and the map will fall back to UNILORIN's center for them. This is a
known temporary limitation (see map.js FALLBACK_CENTER comment).

=== IDEMPOTENCY / SAFETY ===

  - Skips any campus where lat OR lng is already set. Never overwrites
    an admin-entered coordinate with a seed value.
  - Skips any entry whose university or campus slug does not exist,
    printing a warning. Does not abort the whole run for a single
    missing entry — remaining entries still process.
  - Single transaction; rollback on any exception.
  - Non-deleting. Never removes or alters any other column.
"""
import os
import sys

# Allow `python scripts/seed_campus_coordinates.py` from the project root
# without requiring PYTHONPATH to be set.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import University, Campus


# (university_slug, campus_slug, lat, lng)
SEED = [
    ("unilorin", "main",  8.4826,  4.6736),
    ("unilag",   "akoka", 6.51821, 3.39556),
]


def main():
    app = create_app()
    with app.app_context():
        updated = 0
        skipped_populated = 0
        skipped_missing = 0

        try:
            for uni_slug, campus_slug, lat, lng in SEED:
                university = University.query.filter_by(slug=uni_slug).first()
                if university is None:
                    print(
                        f"WARN: university slug='{uni_slug}' not found; "
                        f"skipping {uni_slug}/{campus_slug}."
                    )
                    skipped_missing += 1
                    continue

                campus = Campus.query.filter_by(
                    university_id=university.id,
                    slug=campus_slug,
                ).first()
                if campus is None:
                    print(
                        f"WARN: campus {uni_slug}/{campus_slug} not found; "
                        f"skipping."
                    )
                    skipped_missing += 1
                    continue

                if campus.lat is not None or campus.lng is not None:
                    skipped_populated += 1
                    continue

                campus.lat = lat
                campus.lng = lng
                updated += 1

            db.session.commit()
        except Exception:
            db.session.rollback()
            print("Seed failed — transaction rolled back.")
            raise

        print(f"Campuses updated: {updated}")
        print(f"Skipped (already populated): {skipped_populated}")
        print(f"Skipped (missing university/campus): {skipped_missing}")
        print(
            "NOTE: UNILAG Akoka coordinates are approximate. "
            "See module docstring before production use."
        )


if __name__ == "__main__":
    main()