"""Seed campus center coordinates for campuses with verified data.

DEV / PILOT ONLY.

Coordinates here are for the initial two campuses with real pilot data:
  - UNILORIN 'main'  (existing 39 locations — campus center known)
  - UNILAG  'akoka'  (pilot from Phase 3.2 — approximate, see Phase 3.2 docstring)

Other campuses remain NULL until verified. The map will fall back to
UNILORIN's coordinates (temporary) for those, until a Phase 3.4
addresses per-campus defaults properly.

Idempotent: skips any campus whose lat/lng is already set. Never
overwrites a populated value.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import University, Campus


SEED = [
    # (university_slug, campus_slug, lat, lng)
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
                uni = University.query.filter_by(slug=uni_slug).first()
                if uni is None:
                    print(f"WARN: university slug='{uni_slug}' not found; skipping.")
                    skipped_missing += 1
                    continue

                campus = Campus.query.filter_by(
                    university_id=uni.id, slug=campus_slug
                ).first()
                if campus is None:
                    print(f"WARN: campus {uni_slug}/{campus_slug} not found; skipping.")
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
        print(f"Campuses skipped (already populated): {skipped_populated}")
        print(f"Campuses skipped (missing university/campus): {skipped_missing}")


if __name__ == "__main__":
    main()