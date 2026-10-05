"""DEV ONLY. Seeds a starter set of UNILORIN locations.

Requires FLASK_ENV=development and an existing 'unilorin' university/campus.
Idempotent: skips locations that already exist by name.
"""
import os
from app import create_app
from app.extensions import db
from app.models import University, Campus, Location
from app.maps import categories as loc_cats


SEED = [
    # (name, category, lat, lng, description)
    ("Main Library",            "library",      8.4826, 4.6736, "Central library"),
    ("Faculty of Science",      "building",     8.4802, 4.6735, None),
    ("Faculty of Arts",         "building",     8.4800, 4.6752, None),
    ("Faculty of Engineering",  "building",     8.4795, 4.6703, None),
    ("Faculty of CIS",          "building",     8.4831, 4.6740, "Communication and Information Sciences"),
    ("Student Union Building",  "landmark",     8.4838, 4.6758, "SUB"),
    ("Main Auditorium",         "lecture_hall", 8.4840, 4.6743, None),
    ("University Clinic",       "clinic",       8.4820, 4.6770, None),
    ("GTBank ATM",              "atm",          8.4843, 4.6728, None),
    ("UBA ATM",                 "atm",          8.4822, 4.6768, None),
    ("First Bank ATM",          "atm",          8.4805, 4.6730, None),
    ("Old Cafeteria",           "cafeteria",    8.4833, 4.6722, None),
    ("New Cafeteria",           "cafeteria",    8.4816, 4.6760, None),
    ("Food Court",              "restaurant",   8.4827, 4.6772, None),
    ("Sub Post Office",         "shop",         8.4836, 4.6748, None),
    ("Printing Press",          "printing",     8.4811, 4.6745, "Documents and photocopy"),
    ("Main Gate",               "landmark",     8.4863, 4.6703, "Main entrance"),
    ("Tanke Gate",              "landmark",     8.4768, 4.6715, None),
    ("Bus Terminal",            "transport",    8.4858, 4.6712, "Campus shuttle"),
    ("Sports Complex",          "sports",       8.4782, 4.6783, None),
    ("Chapel",                  "worship",      8.4818, 4.6790, None),
    ("Mosque",                  "worship",      8.4831, 4.6798, None),
    ("Senior Staff Quarters",   "hostel",       8.4808, 4.6805, None),
    ("Female Hostel Area",      "hostel",       8.4798, 4.6810, None),
    ("Male Hostel Area",        "hostel",       8.4788, 4.6815, None),
    ("Postgraduate School",     "building",     8.4835, 4.6750, None),
    ("Faculty of Education",    "building",     8.4790, 4.6745, None),
    ("Faculty of Law",          "building",     8.4825, 4.6765, None),
    ("Faculty of Agriculture",  "building",     8.4788, 4.6728, None),
    ("Faculty of Social Sciences", "building",  8.4820, 4.6755, None),
    ("Unilorin Secondary School", "building",   8.4770, 4.6735, None),
    ("University Bookshop",     "shop",         8.4834, 4.6745, None),
    ("Zenith Bank ATM",         "atm",          8.4830, 4.6725, None),
    ("Amphitheatre",            "lecture_hall", 8.4845, 4.6730, None),
    ("Computer Science Lab",    "lab",          8.4832, 4.6742, None),
    ("Chemistry Lab",           "lab",          8.4805, 4.6738, None),
    ("Physics Lab",             "lab",          8.4800, 4.6740, None),
    ("Biology Lab",             "lab",          8.4802, 4.6742, None),
]


def main():
    assert os.getenv("FLASK_ENV") == "development", \
        "seed_locations.py refuses to run outside development."

    app = create_app()
    with app.app_context():
        uni = University.query.filter_by(slug="unilorin").first()
        if not uni:
            print("ERROR: No 'unilorin' university found. Run seed_dev first.")
            return

        campus = Campus.query.filter_by(university_id=uni.id).first()
        if not campus:
            print("ERROR: No campus found for UNILORIN.")
            return

        existing = {loc.name for loc in Location.query.filter_by(campus_id=campus.id).all()}
        added = 0
        skipped = 0

        for name, category, lat, lng, description in SEED:
            if name in existing:
                skipped += 1
                continue
            if not loc_cats.is_valid(category):
                print(f"  SKIP (bad category): {name} / {category}")
                continue

            wkt_point = f"SRID=4326;POINT({lng} {lat})"
            loc = Location(
                campus_id=campus.id,
                name=name,
                category=category,
                description=description,
                point=wkt_point,
                source="admin",
                status="approved",
            )
            db.session.add(loc)
            added += 1

        db.session.commit()
        print(f"Added {added} locations, skipped {skipped} existing.")
        total = Location.query.filter_by(campus_id=campus.id).count()
        print(f"Total locations in {campus.name}: {total}")


if __name__ == "__main__":
    main()