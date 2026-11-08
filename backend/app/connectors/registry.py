from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import ConnectorAccount
from .base import CloudConnector, ConnectorError
from .google_drive import GoogleDriveConnector
from .local import LocalFolderConnector
from .oauth import get_access_token
from .onedrive import OneDriveConnector

CLOUD_PROVIDERS = {"google_drive": GoogleDriveConnector, "onedrive": OneDriveConnector}


def detect_provider(link: str) -> str:
    l = link.lower()
    if "drive.google.com" in l or "docs.google.com" in l:
        return "google_drive"
    if "1drv.ms" in l or "onedrive" in l or "sharepoint.com" in l:
        return "onedrive"
    if l.startswith("local://"):
        return "local"
    raise ConnectorError("Unrecognised folder link. Paste a Google Drive (or OneDrive) folder link.")


def get_connector(db: Session, user_id: str, provider: str) -> CloudConnector:
    if provider == "local":
        s = get_settings()
        if not s.allow_local_connector:
            raise ConnectorError("Local connector is disabled on this server")
        return LocalFolderConnector(s.local_connector_root)
    if provider not in CLOUD_PROVIDERS:
        raise ConnectorError(f"Unsupported provider {provider}")
    acct = db.query(ConnectorAccount).filter_by(user_id=user_id, provider=provider).one_or_none()
    if acct is None:
        raise ConnectorError(f"Connect your {provider.replace('_', ' ').title()} account first")
    return CLOUD_PROVIDERS[provider](lambda: get_access_token(db, acct))
