from flask_login import UserMixin

from app.extensions import db
from app.models.mixins import UUIDMixin, TimestampMixin, SoftDeleteMixin

ROLES = ("student", "moderator", "campus_admin", "platform_admin")


class User(UUIDMixin, TimestampMixin, SoftDeleteMixin, UserMixin, db.Model):
    __tablename__ = "users"

    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(32), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(80), nullable=False)
    role = db.Column(db.String(32), nullable=False, default="student")
    status = db.Column(db.String(24), nullable=False, default="active")  # active|suspended|blocked
    email_verified_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Relationships
    profile = db.relationship("StudentProfile", back_populates="user",
                              uselist=False, cascade="all, delete-orphan")
    trust = db.relationship("TrustScore", back_populates="user",
                            uselist=False, cascade="all, delete-orphan")
    sessions = db.relationship("UserSession", back_populates="user",
                               cascade="all, delete-orphan")

    @property
    def is_active(self) -> bool:  # Flask-Login uses this
        return self.status == "active" and self.deleted_at is None

    @property
    def has_onboarded(self) -> bool:
        return self.profile is not None and self.profile.programme_id is not None


class StudentProfile(UUIDMixin, TimestampMixin, db.Model):
    __tablename__ = "student_profiles"

    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"),
                        unique=True, nullable=False)
    university_id = db.Column(db.String(36), db.ForeignKey("universities.id"), nullable=False)
    campus_id = db.Column(db.String(36), db.ForeignKey("campuses.id"), nullable=True)
    faculty_id = db.Column(db.String(36), db.ForeignKey("faculties.id"), nullable=True)
    department_id = db.Column(db.String(36), db.ForeignKey("departments.id"), nullable=True)
    programme_id = db.Column(db.String(36), db.ForeignKey("programmes.id"), nullable=True)
    level_id = db.Column(db.String(36), db.ForeignKey("levels.id"), nullable=True)

    matric_no = db.Column(db.String(32), nullable=True)  # unverified
    avatar_key = db.Column(db.String(255), nullable=True)

    user = db.relationship("User", back_populates="profile")


class TrustScore(UUIDMixin, TimestampMixin, db.Model):
    __tablename__ = "trust_scores"

    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"),
                        unique=True, nullable=False)
    score = db.Column(db.Integer, nullable=False, default=0)
    tier = db.Column(db.String(24), nullable=False, default="new")
    accurate_reports = db.Column(db.Integer, nullable=False, default=0)
    false_reports = db.Column(db.Integer, nullable=False, default=0)
    confirmations_given = db.Column(db.Integer, nullable=False, default=0)
    confirmations_received = db.Column(db.Integer, nullable=False, default=0)
    abuse_flags = db.Column(db.Integer, nullable=False, default=0)

    user = db.relationship("User", back_populates="trust")


class UserSession(UUIDMixin, TimestampMixin, db.Model):
    __tablename__ = "user_sessions"

    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    token_hash = db.Column(db.String(128), nullable=False, unique=True)
    ip = db.Column(db.String(64))
    user_agent = db.Column(db.String(255))
    revoked_at = db.Column(db.DateTime(timezone=True))

    user = db.relationship("User", back_populates="sessions")