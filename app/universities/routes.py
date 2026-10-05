from flask import Blueprint, render_template, redirect, url_for, request, jsonify
from flask_login import login_required, current_user

from app.extensions import db
from app.models import University, Campus, Faculty, Department, Programme, Level, StudentProfile

bp = Blueprint("universities", __name__, url_prefix="/onboarding")


@bp.get("/")
@login_required
def onboarding():
    if current_user.has_onboarded:
        return redirect(url_for("web.home"))
    universities = University.query.filter_by(is_active=True).order_by(University.name).all()
    return render_template("pages/onboarding/step1_university.html", universities=universities)


@bp.post("/university")
@login_required
def choose_university():
    uni_id = request.form.get("university_id")
    uni = University.query.get_or_404(uni_id)
    profile = current_user.profile or StudentProfile(user_id=current_user.id,
                                                    university_id=uni.id)
    profile.university_id = uni.id
    if not current_user.profile:
        db.session.add(profile)
    db.session.commit()
    return redirect(url_for("universities.choose_campus"))


@bp.get("/campus")
@login_required
def choose_campus():
    profile = current_user.profile
    if not profile:
        return redirect(url_for("universities.onboarding"))
    campuses = Campus.query.filter_by(university_id=profile.university_id).order_by(Campus.name).all()
    return render_template("pages/onboarding/step2_campus.html", campuses=campuses)


@bp.post("/campus")
@login_required
def set_campus():
    profile = current_user.profile
    campus = Campus.query.get_or_404(request.form["campus_id"])
    profile.campus_id = campus.id
    db.session.commit()
    return redirect(url_for("universities.choose_faculty"))


@bp.get("/faculty")
@login_required
def choose_faculty():
    profile = current_user.profile
    faculties = Faculty.query.filter_by(campus_id=profile.campus_id).order_by(Faculty.name).all()
    return render_template("pages/onboarding/step3_faculty.html", faculties=faculties)


@bp.post("/faculty")
@login_required
def set_faculty():
    profile = current_user.profile
    profile.faculty_id = Faculty.query.get_or_404(request.form["faculty_id"]).id
    db.session.commit()
    return redirect(url_for("universities.choose_department"))


@bp.get("/department")
@login_required
def choose_department():
    profile = current_user.profile
    depts = Department.query.filter_by(faculty_id=profile.faculty_id).order_by(Department.name).all()
    return render_template("pages/onboarding/step4_department.html", departments=depts)


@bp.post("/department")
@login_required
def set_department():
    profile = current_user.profile
    profile.department_id = Department.query.get_or_404(request.form["department_id"]).id
    db.session.commit()
    return redirect(url_for("universities.choose_programme"))


@bp.get("/programme")
@login_required
def choose_programme():
    profile = current_user.profile
    progs = Programme.query.filter_by(department_id=profile.department_id).order_by(Programme.name).all()
    return render_template("pages/onboarding/step5_programme.html", programmes=progs)


@bp.post("/programme")
@login_required
def set_programme():
    profile = current_user.profile
    profile.programme_id = Programme.query.get_or_404(request.form["programme_id"]).id
    db.session.commit()
    return redirect(url_for("universities.choose_level"))


@bp.get("/level")
@login_required
def choose_level():
    profile = current_user.profile
    levels = Level.query.filter_by(programme_id=profile.programme_id).order_by(Level.rank).all()
    return render_template("pages/onboarding/step6_level.html", levels=levels)


@bp.post("/level")
@login_required
def set_level():
    profile = current_user.profile
    profile.level_id = Level.query.get_or_404(request.form["level_id"]).id
    db.session.commit()
    return redirect(url_for("web.home"))


# ── JSON endpoints (used by the onboarding UI later) ─────
@bp.get("/api/campuses/<university_id>")
def api_campuses(university_id):
    rows = Campus.query.filter_by(university_id=university_id).order_by(Campus.name).all()
    return jsonify([{"id": c.id, "name": c.name} for c in rows])


@bp.get("/api/faculties/<campus_id>")
def api_faculties(campus_id):
    rows = Faculty.query.filter_by(campus_id=campus_id).order_by(Faculty.name).all()
    return jsonify([{"id": f.id, "name": f.name} for f in rows])