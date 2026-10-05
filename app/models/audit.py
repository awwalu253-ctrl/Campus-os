from app.extensions import db
from app.models.mixins import UUIDMixin, TimestampMixin


class AuditLog(UUIDMixin, TimestampMixin, db.Model):
    __tablename__ = "audit_logs"

    actor_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"),
                         nullable=True, index=True)
    action = db.Column(db.String(64), nullable=False, index=True)
    entity_type = db.Column(db.String(64), nullable=False)
    entity_id = db.Column(db.String(64), nullable=True)
    before = db.Column(db.JSON, nullable=True)
    after = db.Column(db.JSON, nullable=True)
    ip = db.Column(db.String(64), nullable=True)
    ua = db.Column(db.String(255), nullable=True)