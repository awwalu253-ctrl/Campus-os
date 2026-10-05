from app.extensions import db
from app.models.mixins import UUIDMixin, TimestampMixin


class University(UUIDMixin, TimestampMixin, db.Model):
    __tablename__ = "universities"

    slug = db.Column(db.String(64), unique=True, nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    short_name = db.Column(db.String(32), nullable=False)
    state = db.Column(db.String(64), nullable=True)
    logo_key = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    campuses = db.relationship("Campus", back_populates="university",
                               cascade="all, delete-orphan")


class Campus(UUIDMixin, TimestampMixin, db.Model):
    __tablename__ = "campuses"

    university_id = db.Column(db.String(36), db.ForeignKey("universities.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    slug = db.Column(db.String(64), nullable=False)
    name = db.Column(db.String(160), nullable=False)

    university = db.relationship("University", back_populates="campuses")
    faculties = db.relationship("Faculty", back_populates="campus",
                                cascade="all, delete-orphan")

    __table_args__ = (
        db.UniqueConstraint("university_id", "slug", name="uq_campus_slug_per_uni"),
    )


class Faculty(UUIDMixin, TimestampMixin, db.Model):
    __tablename__ = "faculties"

    campus_id = db.Column(db.String(36), db.ForeignKey("campuses.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    code = db.Column(db.String(24), nullable=True)

    campus = db.relationship("Campus", back_populates="faculties")
    departments = db.relationship("Department", back_populates="faculty",
                                  cascade="all, delete-orphan")


class Department(UUIDMixin, TimestampMixin, db.Model):
    __tablename__ = "departments"

    faculty_id = db.Column(db.String(36), db.ForeignKey("faculties.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    code = db.Column(db.String(24), nullable=True)

    faculty = db.relationship("Faculty", back_populates="departments")
    programmes = db.relationship("Programme", back_populates="department",
                                 cascade="all, delete-orphan")


class Programme(UUIDMixin, TimestampMixin, db.Model):
    __tablename__ = "programmes"

    department_id = db.Column(db.String(36), db.ForeignKey("departments.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    code = db.Column(db.String(24), nullable=True)

    department = db.relationship("Department", back_populates="programmes")
    levels = db.relationship("Level", back_populates="programme",
                             cascade="all, delete-orphan")


class Level(UUIDMixin, TimestampMixin, db.Model):
    __tablename__ = "levels"

    programme_id = db.Column(db.String(36), db.ForeignKey("programmes.id", ondelete="CASCADE"),
                             nullable=False, index=True)
    name = db.Column(db.String(32), nullable=False)   # "100 Level"
    rank = db.Column(db.Integer, nullable=False)      # 100, 200, ...

    programme = db.relationship("Programme", back_populates="levels")

    __table_args__ = (
        db.UniqueConstraint("programme_id", "rank", name="uq_level_rank_per_programme"),
    )