"""OneDrive / SharePoint connector via Microsoft Graph (Phase 3 provider, same interface as Drive)."""
from __future__ import annotations

import base64
import time
from collections.abc import Callable, Iterator

import httpx

from .base import CloudConnector, ConnectorError, RemoteFile

GRAPH = "https://graph.microsoft.com/v1.0"


class OneDriveConnector(CloudConnector):
    provider = "onedrive"

    def __init__(self, token_provider: Callable[[], str], client: httpx.Client | None = None):
        self._token = token_provider
        self._http = client or httpx.Client(timeout=httpx.Timeout(60, read=300), follow_redirects=True)

    def _req(self, method: str, url: str, **kw) -> httpx.Response:
        for attempt in range(5):
            resp = self._http.request(method, url, headers={"Authorization": f"Bearer {self._token()}"}, **kw)
            if resp.status_code in (429, 503, 504):
                time.sleep(int(resp.headers.get("Retry-After", 2 ** attempt)))
                continue
            if resp.status_code in (401, 403, 404):
                raise ConnectorError(f"OneDrive denied access or item not found ({resp.status_code})")
            resp.raise_for_status()
            return resp
        raise ConnectorError("OneDrive is throttling requests; please retry shortly")

    def parse_link(self, link: str) -> str:
        link = link.strip()
        if not link.startswith("https://"):
            raise ConnectorError("Paste the OneDrive folder sharing link (https://...)")
        # Graph "shares" id: u! + unpadded base64url of the sharing URL.
        enc = base64.urlsafe_b64encode(link.encode()).decode().rstrip("=")
        item = self._req("GET", f"{GRAPH}/shares/u!{enc}/driveItem").json()
        if "folder" not in item:
            raise ConnectorError("The link points to a file, not a folder")
        return f"{item['parentReference']['driveId']}:{item['id']}"

    def folder_name(self, folder_id: str) -> str:
        drive, item = folder_id.split(":", 1)
        return self._req("GET", f"{GRAPH}/drives/{drive}/items/{item}").json()["name"]

    def walk(self, folder_id: str) -> Iterator[RemoteFile]:
        drive, root = folder_id.split(":", 1)
        stack = [(root, "")]
        while stack:
            item_id, path = stack.pop()
            url = f"{GRAPH}/drives/{drive}/items/{item_id}/children?$top=999"
            while url:
                data = self._req("GET", url).json()
                for it in data.get("value", []):
                    if "folder" in it:
                        stack.append((it["id"], f"{path}/{it['name']}".strip("/")))
                    elif "file" in it:
                        yield RemoteFile(id=f"{drive}:{it['id']}", name=it["name"], path=path,
                                         mime_type=it["file"].get("mimeType", ""), size=it.get("size", 0),
                                         modified_time=it.get("lastModifiedDateTime", ""),
                                         checksum=(it["file"].get("hashes") or {}).get("sha256Hash", ""))
                url = data.get("@odata.nextLink")

    def download(self, f: RemoteFile) -> tuple[bytes, str]:
        drive, item = f.id.split(":", 1)
        return self._req("GET", f"{GRAPH}/drives/{drive}/items/{item}/content").content, f.name

    def upload(self, folder_id: str, filename: str, data: bytes, mime_type: str) -> str:
        drive, item = folder_id.split(":", 1)
        r = self._req("PUT", f"{GRAPH}/drives/{drive}/items/{item}:/{filename}:/content",
                      content=data, headers={"Content-Type": mime_type})
        return r.json()["id"]
