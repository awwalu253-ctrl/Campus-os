"""DEV ONLY. Seeds a UNILORIN-like university hierarchy for local testing.

Refuses to run unless FLASK_ENV=development.
"""
import os
from app import create_app
from app.extensions import db
from app.models import University, Campus, Faculty, Department, Programme, Level


def main():
    assert os.getenv("FLASK_ENV") == "development", \
        "seed_dev.py refuses to run outside development."

    app = create_app()
    with app.app_context():
        if University.query.filter_by(slug="unilorin").first():
            print("Already seeded.")
            return

        uni = University(
            slug="unilorin", name="University of Ilorin",
            short_name="UNILORIN", state="Kwara",
        )
        db.session.add(uni); db.session.flush()

        main_campus = Campus(university_id=uni.id, slug="main", name="Main Campus")
        db.session.add(main_campus); db.session.flush()

        # Two faculties, one department each — enough to test the flow.
        cis = Faculty(campus_id=main_campus.id, name="Faculty of Communication and Information Sciences", code="CIS")
        eng = Faculty(campus_id=main_campus.id, name="Faculty of Engineering and Technology", code="FET")
        db.session.add_all([cis, eng]); db.session.flush()

        cs = Department(faculty_id=cis.id, name="Computer Science", code="CSC")
        mech = Department(faculty_id=eng.id, name="Mechanical Engineering", code="MEE")
        db.session.add_all([cs, mech]); db.session.flush()

        cs_prog = Programme(department_id=cs.id, name="B.Sc. Computer Science", code="CSC")
        mech_prog = Programme(department_id=mech.id, name="B.Eng. Mechanical Engineering", code="MEE")
        db.session.add_all([cs_prog, mech_prog]); db.session.flush()

        for prog in (cs_prog, mech_prog):
            for rank in (100, 200, 300, 400, 500):
                db.session.add(Level(programme_id=prog.id, name=f"{rank} Level", rank=rank))

        db.session.commit()
        print("Seeded UNILORIN dev data.")


if __name__ == "__main__":
    main()