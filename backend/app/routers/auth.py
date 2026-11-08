import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..audit import audit
from ..config import get_settings
from ..db import get_db
from ..deps import AGENT_PREFIX, client_ip, current_user
from ..models import AgentToken, RefreshSession, User
from ..schemas import LoginIn, ProfileIn, RefreshIn, RegisterIn, TokenOut, UserOut
from ..security import create_access_token, hash_password, hash_token, new_refresh_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
PROFILE_KEYS = {"name", "designation", "firm", "licence_number", "address", "phone", "email", "gstin",
                "bank_details", "place"}


def _issue(db: Session, user: User, device: str = "") -> TokenOut:
    raw, hashed = new_refresh_token()
    s = get_settings()
    db.add(RefreshSession(user_id=user.id, token_hash=hashed, device=device[:255],
                          expires_at=datetime.now(timezone.utc) + timedelta(days=s.refresh_token_days)))
    db.commit()
    return TokenOut(access_token=create_access_token(user.id), refresh_token=raw,
                    expires_in=s.access_token_minutes * 60)


@router.post("/register", response_model=TokenOut)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    count = db.query(func.count(User.id)).scalar()
    if count and not get_settings().allow_registration:
        raise HTTPException(403, "Registration is closed")
    if db.query(User).filter_by(email=body.email).first():
        raise HTTPException(409, "Email already registered")
    user = User(email=body.email, password_hash=hash_password(body.password), full_name=body.full_name,
                is_admin=(count == 0), investigator_profile={"name": body.full_name} if body.full_name else {})
    db.add(user)
    db.commit()
    audit(db, "auth.register", user.id, ip=client_ip(request))
    return _issue(db, user)


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=body.email.strip().lower()).first()
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        audit(db, "auth.login_failed", None, ip=client_ip(request), email=body.email)
        db.commit()
        raise HTTPException(401, "Incorrect email or password")
    audit(db, "auth.login", user.id, ip=client_ip(request), device=body.device)
    return _issue(db, user, body.device)


@router.post("/refresh", response_model=TokenOut)
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    sess = db.query(RefreshSession).filter_by(token_hash=hash_token(body.refresh_token)).first()
    exp = sess.expires_at.replace(tzinfo=timezone.utc) if sess and sess.expires_at.tzinfo is None else (
        sess.expires_at if sess else None)
    if not sess or sess.revoked or exp < datetime.now(timezone.utc):
        raise HTTPException(401, "Session expired, please sign in again")
    sess.revoked = True  # rotation: every refresh token is single-use
    user = db.get(User, sess.user_id)
    return _issue(db, user, sess.device)


@router.post("/logout")
def logout(body: RefreshIn, db: Session = Depends(get_db)):
    sess = db.query(RefreshSession).filter_by(token_hash=hash_token(body.refresh_token)).first()
    if sess:
        sess.revoked = True
        db.commit()
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.put("/me", response_model=UserOut)
def update_me(body: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.full_name is not None:
        user.full_name = body.full_name
    if body.investigator_profile is not None:
        user.investigator_profile = {k: v.strip() for k, v in body.investigator_profile.items()
                                     if k in PROFILE_KEYS and v and v.strip()}
    db.commit()
    return user


# ------------------------------------------------------------------ Claude Code access tokens
@router.post("/agent-tokens")
def create_agent_token(body: dict, request: Request, user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    """Create a token for the user's Claude Code session. Shown once; store it as an environment secret."""
    if request.headers.get("authorization", "").split(" ")[-1].startswith(AGENT_PREFIX):
        raise HTTPException(403, "Agent tokens cannot create other tokens")
    raw = AGENT_PREFIX + secrets.token_urlsafe(40)
    tok = AgentToken(user_id=user.id, name=str(body.get("name") or "Claude Code")[:128], token_hash=hash_token(raw))
    db.add(tok)
    audit(db, "auth.agent_token_created", user.id, name=tok.name)
    db.commit()
    return {"id": tok.id, "name": tok.name, "token": raw}


@router.get("/agent-tokens")
def list_agent_tokens(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"id": t.id, "name": t.name, "created_at": t.created_at, "last_used_at": t.last_used_at}
            for t in db.query(AgentToken).filter_by(user_id=user.id, revoked=False).order_by(AgentToken.created_at)]


@router.delete("/agent-tokens/{token_id}")
def revoke_agent_token(token_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    tok = db.get(AgentToken, token_id)
    if tok and tok.user_id == user.id:
        tok.revoked = True
        audit(db, "auth.agent_token_revoked", user.id, name=tok.name)
        db.commit()
    return {"ok": True}
