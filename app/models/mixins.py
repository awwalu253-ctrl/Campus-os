import uuid
from datetime import datetime, timezone

from app.extensions import db


def _uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UUIDMixin:
    id = db.Column(db.String(36), primary_key=True, default=_uuid)


class TimestampMixin:
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow,
                           onupdate=utcnow, nullable=False)


class SoftDeleteMixin:
    deleted_at = db.Column(db.DateTime(timezone=True), nullable=True)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None