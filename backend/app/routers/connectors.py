from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..audit import audit
from ..config import get_settings
from ..connectors.base import ConnectorError
from ..connectors.oauth import build_authorize_url, complete_authorization, revoke
from ..db import get_db
from ..deps import current_user
from ..models import ConnectorAccount, User
from ..schemas import ConnectorOut

router = APIRouter(prefix="/connectors", tags=["connectors"])
PROVIDERS = ["google_drive", "onedrive"]


@router.get("", response_model=list[ConnectorOut])
def list_connectors(user: User = Depends(current_user), db: Session = Depends(get_db)):
    s = get_settings()
    configured = {"google_drive": bool(s.google_client_id), "onedrive": bool(s.microsoft_client_id)}
    accts = {a.provider: a for a in db.query(ConnectorAccount).filter_by(user_id=user.id)}
    out = [ConnectorOut(provider=p, connected=p in accts, account_email=accts[p].account_email if p in accts else "",
                        configured=configured[p]) for p in PROVIDERS]
    if s.allow_local_connector:
        out.append(ConnectorOut(provider="local", connected=True, configured=True, account_email="server folder"))
    return out


@router.post("/{provider}/authorize")
def authorize(provider: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if provider not in PROVIDERS:
        raise HTTPException(404, "Unknown provider")
    try:
        return {"authorize_url": build_authorize_url(db, user.id, provider),
                "callback_scheme": get_settings().ios_callback_scheme}
    except ConnectorError as e:
        raise HTTPException(400, str(e))


@router.get("/{provider}/callback", include_in_schema=False)
def callback(provider: str, state: str = "", code: str = "", error: str = "", db: Session = Depends(get_db)):
    scheme = get_settings().ios_callback_scheme
    if error or not code:
        return RedirectResponse(f"{scheme}://oauth-complete?provider={provider}&status=error&message={quote(error or 'cancelled')}")
    try:
        acct = complete_authorization(db, provider, state, code)
        audit(db, "connector.connected", acct.user_id, provider=provider, account=acct.account_email)
        db.commit()
    except ConnectorError as e:
        return RedirectResponse(f"{scheme}://oauth-complete?provider={provider}&status=error&message={quote(str(e))}")
    return RedirectResponse(f"{scheme}://oauth-complete?provider={provider}&status=ok")


@router.delete("/{provider}")
def disconnect(provider: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    acct = db.query(ConnectorAccount).filter_by(user_id=user.id, provider=provider).one_or_none()
    if acct:
        revoke(db, acct)
        audit(db, "connector.disconnected", user.id, provider=provider)
        db.commit()
    return {"ok": True}


@router.get("/oauth-landing", include_in_schema=False, response_class=HTMLResponse)
def landing():
    return "<p>You can return to Bharati Investigation Desk.</p>"
