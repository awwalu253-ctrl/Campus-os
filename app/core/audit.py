from app.extensions import db
from app.models.audit import AuditLog


def log(actor_id, action: str, entity_type: str, entity_id, *, before=None, after=None):
    """Write a single audit row. Caller owns the transaction."""
    db.session.add(AuditLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        before=before,
        after=after,
    ))