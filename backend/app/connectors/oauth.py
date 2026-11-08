"""OAuth 2.0 authorisation-code flow with PKCE for cloud connectors.

The iOS app never sees provider tokens: it opens the authorize URL in ASWebAuthenticationSession, the
provider redirects to this backend, the backend stores the encrypted refresh token and redirects to
bharatidesk://oauth-complete so the app can close the browser sheet.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import ConnectorAccount, OAuthState
from ..security import decrypt_str, encrypt_str
from .base import ConnectorError

PROVIDERS = {
    "google_drive": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        # Least privilege that still allows reading a pasted folder link and uploading the report back:
        # drive.readonly = read files the user can access; drive.file = create files this app uploads.
        "scopes": "openid email https://www.googleapis.com/auth/drive.readonly https://www.googleapis.com/auth/drive.file",
        "extra": {"access_type": "offline", "prompt": "consent", "include_granted_scopes": "true"},
    },
    "onedrive": {
        "auth_url": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        "scopes": "offline_access openid email Files.Read.All Files.ReadWrite",
        "extra": {},
    },
}


def _client(provider: str) -> tuple[str, str]:
    s = get_settings()
    if provider == "google_drive":
        cid, sec = s.google_client_id, s.google_client_secret
    elif provider == "onedrive":
        cid, sec = s.microsoft_client_id, s.microsoft_client_secret
    else:
        raise ConnectorError(f"Unknown provider {provider}")
    if not cid:
        raise ConnectorError(f"{provider} is not configured on the server (missing client id)")
    return cid, sec


def _urls(provider: str) -> dict:
    p = dict(PROVIDERS[provider])
    tenant = get_settings().microsoft_tenant
    p["auth_url"] = p["auth_url"].format(tenant=tenant)
    p["token_url"] = p["token_url"].format(tenant=tenant)
    return p


def redirect_uri(provider: str) -> str:
    return f"{get_settings().public_base_url.rstrip('/')}/api/v1/connectors/{provider}/callback"


def build_authorize_url(db: Session, user_id: str, provider: str) -> str:
    cid, _ = _client(provider)
    p = _urls(provider)
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    db.add(OAuthState(state=state, user_id=user_id, provider=provider, code_verifier=verifier))
    db.commit()
    params = {
        "client_id": cid, "redirect_uri": redirect_uri(provider), "response_type": "code",
        "scope": p["scopes"], "state": state, "code_challenge": challenge, "code_challenge_method": "S256",
        **p["extra"],
    }
    return p["auth_url"] + "?" + urlencode(params)


def complete_authorization(db: Session, provider: str, state: str, code: str) -> ConnectorAccount:
    st = db.get(OAuthState, state)
    if not st or st.provider != provider:
        raise ConnectorError("Invalid or expired OAuth state")
    created = st.created_at if st.created_at.tzinfo else st.created_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - created > timedelta(minutes=15):
        db.delete(st); db.commit()
        raise ConnectorError("OAuth state expired, please try again")
    cid, sec = _client(provider)
    p = _urls(provider)
    resp = httpx.post(p["token_url"], data={
        "client_id": cid, "client_secret": sec, "code": code, "code_verifier": st.code_verifier,
        "grant_type": "authorization_code", "redirect_uri": redirect_uri(provider),
    }, timeout=30)
    if resp.status_code != 200:
        raise ConnectorError(f"Token exchange failed: {resp.text[:300]}")
    tok = resp.json()
    email = _email_from_id_token(tok.get("id_token", ""))
    acct = db.query(ConnectorAccount).filter_by(user_id=st.user_id, provider=provider).one_or_none()
    if acct is None:
        acct = ConnectorAccount(user_id=st.user_id, provider=provider)
        db.add(acct)
    acct.account_email = email
    if tok.get("refresh_token"):
        acct.refresh_token_enc = encrypt_str(tok["refresh_token"])
    acct.access_token_enc = encrypt_str(tok["access_token"])
    acct.access_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(tok.get("expires_in", 3600)) - 60)
    acct.scopes = tok.get("scope", "")
    db.delete(st)
    db.commit()
    return acct


def _email_from_id_token(id_token: str) -> str:
    if not id_token:
        return ""
    try:
        payload = id_token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        import json
        return json.loads(base64.urlsafe_b64decode(payload)).get("email", "")
    except Exception:
        return ""


def get_access_token(db: Session, acct: ConnectorAccount) -> str:
    exp = acct.access_expires_at
    if exp and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if acct.access_token_enc and exp and exp > datetime.now(timezone.utc):
        return decrypt_str(acct.access_token_enc)
    if not acct.refresh_token_enc:
        raise ConnectorError("Cloud account needs to be reconnected")
    cid, sec = _client(acct.provider)
    p = _urls(acct.provider)
    resp = httpx.post(p["token_url"], data={
        "client_id": cid, "client_secret": sec, "grant_type": "refresh_token",
        "refresh_token": decrypt_str(acct.refresh_token_enc),
    }, timeout=30)
    if resp.status_code != 200:
        raise ConnectorError("Cloud authorisation expired or was revoked; please reconnect the account")
    tok = resp.json()
    acct.access_token_enc = encrypt_str(tok["access_token"])
    if tok.get("refresh_token"):
        acct.refresh_token_enc = encrypt_str(tok["refresh_token"])
    acct.access_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(tok.get("expires_in", 3600)) - 60)
    db.commit()
    return tok["access_token"]


def revoke(db: Session, acct: ConnectorAccount) -> None:
    """Best-effort revoke at the provider, then delete our stored tokens."""
    if acct.provider == "google_drive" and acct.refresh_token_enc:
        try:
            httpx.post("https://oauth2.googleapis.com/revoke",
                       params={"token": decrypt_str(acct.refresh_token_enc)}, timeout=15)
        except Exception:
            pass
    db.delete(acct)
    db.commit()
