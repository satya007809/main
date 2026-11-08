from sqlalchemy.orm import Session

from .models import AuditLog


def audit(db: Session, action: str, user_id: str | None = None, case_id: str | None = None,
          ip: str = "", **detail) -> None:
    db.add(AuditLog(action=action, user_id=user_id, case_id=case_id, detail=detail, ip=ip))
