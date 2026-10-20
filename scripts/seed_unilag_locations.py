"""Seed two verified pilot locations on UNILAG's Akoka campus.

DEV / PILOT ONLY.

This is a first, small footprint of location data outside UNILORIN. The
goal is to prove the map pipeline works for a second campus before any
larger expansion. Two locations are seeded:

  1. University of Lagos Library  (category: library)
  2. Main Campus (Akoka)          (category: landmark)

=== COORDINATE CAVEAT ===

The coordinates below are APPROXIMATE and NOT yet verified against an
official UNILAG source. They are used for development testing only.

  - Library:    6.52272, 3.40063  (third-party map data)
  - Akoka:      6.51821, 3.39556  (OpenStreetMap)

Do not present these as production-verified. Before any user-facing
rollout of this data, the coordinates must be checked against:

  - Official UNILAG campus maps (unilag.edu.ng), or
  - A physical survey, or
  - A paid/reputable geocoding service with an official-level accuracy
    guarantee.

Until then, treat this seed as a technical validation of the pipeline,
not as ground truth.

=== IDEMPOTENCY / SAFETY ===

  - Aborts safely if the 'unilag' university or 'akoka' campus is
    missing or ambiguous.
  - Skips any location whose (campus_id, name) already exists.
  - Never overwrites, never deletes.
  - Single transaction; rollback on any exception.
  - Categories are validated against app.maps.categories.
"""
import os
import sys

# Allow `python scripts/seed_unilag_locations.py` from the project root
# without requiring PYTHONPATH to be set.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.maps import categories as loc_cats
from app.maps.models import Location
from app.models import University, Campus


# (name, category, lat, lng, description)
# Coordinates are approximate; see the module docstring for the caveat.
SEED = [
    (
        "University of Lagos Library",
        "library",
        6.52272,
        3.40063,
        "Main library at Akoka campus. Coordinates approximate.",
    ),
    (
        "Main Campus (Akoka)",
        "landmark",
        6.51821,
        3.39556,
        "Akoka campus landmark. Coordinates approximate.",
    ),
]


def main():
    app = create_app()
    with app.app_context():
        # ── Resolve UNILAG ──────────────────────────────
        unilag_matches = University.query.filter_by(slug="unilag").all()
        if len(unilag_matches) == 0:
            print("ERROR: no university with slug='unilag' found. Aborting.")
            return
        if len(unilag_matches) > 1:
            print(
                f"ERROR: slug='unilag' is ambiguous "
                f"({len(unilag_matches)} matches). Aborting."
            )
            return
        university = unilag_matches[0]

        # ── Resolve Akoka campus under UNILAG ───────────
        campus_matches = Campus.query.filter_by(
            university_id=university.id,
            slug="akoka",
        ).all()
        if len(campus_matches) == 0:
            print(
                "ERROR: no campus with slug='akoka' under UNILAG. Aborting."
            )
            return
        if len(campus_matches) > 1:
            print(
                f"ERROR: slug='akoka' is ambiguous under UNILAG "
                f"({len(campus_matches)} matches). Aborting."
            )
            return
        campus = campus_matches[0]

        # ── Validate all seed categories up front ───────
        bad_categories = [
            row[1] for row in SEED if not loc_cats.is_valid(row[1])
        ]
        if bad_categories:
            print(
                "ERROR: unknown category(ies) in SEED: "
                f"{bad_categories}. Aborting."
            )
            return

        # ── Insert (idempotent, non-overwriting) ────────
        added = 0
        skipped = 0
        try:
            for name, category, lat, lng, description in SEED:
                existing = Location.query.filter_by(
                    campus_id=campus.id,
                    name=name,
                ).first()
                if existing is not None:
                    skipped += 1
                    continue

                wkt_point = f"SRID=4326;POINT({lng} {lat})"
                db.session.add(Location(
                    campus_id=campus.id,
                    name=name,
                    category=category,
                    description=description,
                    point=wkt_point,
                    source="admin",
                    status="approved",
                ))
                added += 1

            db.session.commit()
        except Exception:
            db.session.rollback()
            print("Seed failed — transaction rolled back.")
            raise

        total = Location.query.filter_by(campus_id=campus.id).count()
        print(
            f"UNILAG Akoka: added {added}, skipped {skipped} existing."
        )
        print(f"Total locations in UNILAG Akoka: {total}")
        print(
            "NOTE: coordinates are approximate; see module docstring for "
            "verification requirements before production use."
        )


if __name__ == "__main__":
    main()