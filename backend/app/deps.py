from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .db import get_db
from .models import AgentToken, Case, User, utcnow
from .security import decode_access_token, hash_token

AGENT_PREFIX = "bid_at_"

bearer = HTTPBearer(auto_error=False)


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    raw = creds.credentials
    if raw.startswith(AGENT_PREFIX):
        tok = db.query(AgentToken).filter_by(token_hash=hash_token(raw), revoked=False).first()
        uid = tok.user_id if tok else None
        if tok:
            tok.last_used_at = utcnow()
            db.commit()
    else:
        uid = decode_access_token(raw)
    user = db.get(User, uid) if uid else None
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access required")
    return user


def owned_case(case_id: str, user: User, db: Session) -> Case:
    case = db.get(Case, case_id)
    # Cases are private to their owner (admins included: access is never implied by role).
    if case is None or case.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    return case


def client_ip(request: Request) -> str:
    return request.headers.get("x-forwarded-for", request.client.host if request.client else "").split(",")[0]
