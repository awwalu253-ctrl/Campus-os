"""Seed Trinity University and Thomas Adewumi University (universities + campuses only).

Phase 3.8A, Step 1. This file creates ONLY the university and campus
records. Faculties, departments, programmes, and levels will be seeded
in later steps of the same phase, after their source data has been
verified and the onboarding empty states are in place.

=== VERIFIED DATA ===

Trinity University (Yaba, Lagos):
  - Name confirmed on the official site: https://www.trinityuniversity.edu.ng/
  - State: Lagos
  - Single campus assumed at Yaba. No evidence of other campuses.

Thomas Adewumi University (Oko-Irese, Kwara State):
  - Name confirmed on the official site: https://tau.edu.ng/
  - State: Kwara
  - Single campus assumed at Oko-Irese. No evidence of other campuses.

=== UNVERIFIED DETAILS ===

Campus names ("Yaba Campus", "Oko Campus") are DESCRIPTIVE, not
official. Neither university publishes a formal campus name on the
sources consulted. The names were chosen because the location is
documented; the label is our own construction, not an official name.

Coordinates are NOT seeded. Neither official site provides
coordinates. The THE listing for TAU contains a geolocation that
appears to have swapped axes (documented in Phase 3.8A inspection).
Seeding a wrong coordinate would be worse than seeding none.

Because these campuses have no coordinates and no locations, Phase
3.4's empty state will render for their students (verified in
Phase 3.8A Correction 1). No misleading UNILORIN fallback will occur.

=== IDEMPOTENCY / SAFETY ===

  - University matched by slug. Skipped if exists.
  - Campus matched by (university_id, slug). Skipped if exists.
  - Never overwrites. Never deletes.
  - Slug collision with a DIFFERENT name: logs a warning and skips
    the university (does not create the campus either, since the
    parent is ambiguous). Counter 'collisions' tracks this case.
  - Single transaction; rollback on any exception.
"""
import os
import sys

# Allow `python scripts/seed_academic_trinity_tau.py` from the project root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import University, Campus


# Each entry: (slug, name, short_name, state, campuses)
# campuses: list of (campus_slug, campus_name)
# Coordinates are intentionally omitted (see module docstring).
SEED = [
    (
        "trinity",
        "Trinity University, Yaba",
        "Trinity",
        "Lagos",
        [("yaba", "Yaba Campus")],  # descriptive name
    ),
    (
        "tau",
        "Thomas Adewumi University",
        "TAU",
        "Kwara",
        [("oko", "Oko Campus")],  # descriptive name
    ),
]


def main():
    app = create_app()
    with app.app_context():
        added_unis = 0
        skipped_unis = 0
        added_campuses = 0
        skipped_campuses = 0
        collisions = 0

        try:
            for slug, name, short_name, state, campuses in SEED:
                existing = University.query.filter_by(slug=slug).first()

                if existing is not None:
                    if existing.name != name:
                        print(
                            f"WARN: slug '{slug}' already exists with a "
                            f"different name ('{existing.name}' != "
                            f"'{name}'). Skipping this entry."
                        )
                        collisions += 1
                        continue
                    skipped_unis += 1
                    university = existing
                else:
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

                for campus_slug, campus_name in campuses:
                    dup = Campus.query.filter_by(
                        university_id=university.id,
                        slug=campus_slug,
                    ).first()
                    if dup is not None:
                        skipped_campuses += 1
                        continue
                    db.session.add(Campus(
                        university_id=university.id,
                        slug=campus_slug,
                        name=campus_name,
                        # lat, lng intentionally omitted (null)
                    ))
                    added_campuses += 1

            db.session.commit()
        except Exception:
            db.session.rollback()
            print("Seed failed — transaction rolled back.")
            raise

        print(f"Universities: added {added_unis}, skipped {skipped_unis}.")
        print(f"Campuses:     added {added_campuses}, skipped {skipped_campuses}.")
        print(f"Slug collisions (skipped, different name): {collisions}.")
        print(
            "NOTE: campus names 'Yaba Campus' and 'Oko Campus' are "
            "descriptive, not official. Coordinates not seeded; "
            "Phase 3.4 empty state will render for these campuses."
        )


if __name__ == "__main__":
    main()