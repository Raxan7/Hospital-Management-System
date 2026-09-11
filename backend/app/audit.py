from sqlalchemy.orm import Session
from .models import AuditLog, User


def record(db: Session, user: User, action: str, entity: str, entity_id=None, details=None):
    db.add(AuditLog(
        hospital_id=user.hospital_id,
        user_id=user.id,
        action=action,
        entity=entity,
        entity_id=str(entity_id) if entity_id is not None else None,
        details=details or {},
    ))
