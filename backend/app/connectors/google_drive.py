"""Google Drive connector (Drive API v3 over HTTPS)."""
from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Iterator

import httpx

from .base import CloudConnector, ConnectorError, RemoteFile

API = "https://www.googleapis.com/drive/v3"
UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
FOLDER = "application/vnd.google-apps.folder"
SHORTCUT = "application/vnd.google-apps.shortcut"
EXPORTS = {
    "application/vnd.google-apps.document": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
    "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.drawing": ("image/png", ".png"),
}
_LINK_PATTERNS = [
    re.compile(r"/folders/([A-Za-z0-9_-]{10,})"),
    re.compile(r"[?&]id=([A-Za-z0-9_-]{10,})"),
]


class GoogleDriveConnector(CloudConnector):
    provider = "google_drive"

    def __init__(self, token_provider: Callable[[], str], client: httpx.Client | None = None):
        self._token = token_provider
        self._http = client or httpx.Client(timeout=httpx.Timeout(60, read=300))

    # -------------------------------------------------------------- helpers
    def _req(self, method: str, url: str, **kw) -> httpx.Response:
        for attempt in range(5):
            headers = {"Authorization": f"Bearer {self._token()}", **kw.pop("headers", {})}
            resp = self._http.request(method, url, headers=headers, **kw)
            if resp.status_code in (429, 500, 502, 503, 504) or (
                resp.status_code == 403 and "rateLimitExceeded" in resp.text
            ):
                time.sleep(min(2 ** attempt, 20))
                continue
            if resp.status_code == 404:
                raise ConnectorError("Folder or file not found, or your Google account has no access to it")
            if resp.status_code in (401, 403):
                raise ConnectorError(f"Google Drive denied access ({resp.status_code}). "
                                     "Check that the connected account can open this folder.")
            resp.raise_for_status()
            return resp
        raise ConnectorError("Google Drive is rate-limiting requests; please retry shortly")

    def parse_link(self, link: str) -> str:
        link = link.strip()
        for pat in _LINK_PATTERNS:
            m = pat.search(link)
            if m:
                return m.group(1)
        if re.fullmatch(r"[A-Za-z0-9_-]{10,}", link):
            return link
        raise ConnectorError("This does not look like a Google Drive folder link")

    def _meta(self, file_id: str) -> dict:
        return self._req("GET", f"{API}/files/{file_id}", params={
            "fields": "id,name,mimeType,shortcutDetails", "supportsAllDrives": "true"}).json()

    def folder_name(self, folder_id: str) -> str:
        meta = self._meta(folder_id)
        if meta.get("mimeType") != FOLDER:
            raise ConnectorError("The link points to a file, not a folder")
        return meta["name"]

    def _children(self, folder_id: str) -> Iterator[dict]:
        token = None
        while True:
            params = {
                "q": f"'{folder_id}' in parents and trashed = false",
                "fields": "nextPageToken, files(id,name,mimeType,size,modifiedTime,md5Checksum,shortcutDetails)",
                "pageSize": 1000, "supportsAllDrives": "true", "includeItemsFromAllDrives": "true",
            }
            if token:
                params["pageToken"] = token
            data = self._req("GET", f"{API}/files", params=params).json()
            yield from data.get("files", [])
            token = data.get("nextPageToken")
            if not token:
                return

    def walk(self, folder_id: str) -> Iterator[RemoteFile]:
        seen: set[str] = set()
        stack = [(folder_id, "")]
        while stack:
            fid, path = stack.pop()
            if fid in seen:  # protects against shortcut loops
                continue
            seen.add(fid)
            for item in self._children(fid):
                mime = item["mimeType"]
                if mime == SHORTCUT:
                    sd = item.get("shortcutDetails", {})
                    target, mime = sd.get("targetId"), sd.get("targetMimeType", "")
                    if not target:
                        continue
                    item = {**item, "id": target, "mimeType": mime}
                if mime == FOLDER:
                    stack.append((item["id"], f"{path}/{item['name']}".strip("/")))
                    continue
                hint = {}
                if mime in EXPORTS:
                    hint = {"export_mime": EXPORTS[mime][0], "export_ext": EXPORTS[mime][1]}
                elif mime.startswith("application/vnd.google-apps."):
                    hint = {"unsupported_native": True}
                yield RemoteFile(id=item["id"], name=item["name"], path=path, mime_type=mime,
                                 size=int(item.get("size") or 0), modified_time=item.get("modifiedTime", ""),
                                 checksum=item.get("md5Checksum", ""), download_hint=hint)

    def download(self, f: RemoteFile) -> tuple[bytes, str]:
        if f.download_hint.get("unsupported_native"):
            raise ConnectorError(f"Google native type {f.mime_type} cannot be exported")
        if "export_mime" in f.download_hint:
            r = self._req("GET", f"{API}/files/{f.id}/export", params={"mimeType": f.download_hint["export_mime"]})
            name = f.name if f.name.lower().endswith(f.download_hint["export_ext"]) else f.name + f.download_hint["export_ext"]
            return r.content, name
        r = self._req("GET", f"{API}/files/{f.id}", params={"alt": "media", "supportsAllDrives": "true"})
        return r.content, f.name

    def upload(self, folder_id: str, filename: str, data: bytes, mime_type: str) -> str:
        meta = {"name": filename, "parents": [folder_id]}
        files = {
            "metadata": (None, json.dumps(meta), "application/json; charset=UTF-8"),
            "file": (filename, data, mime_type),
        }
        r = self._req("POST", UPLOAD, params={"uploadType": "multipart", "supportsAllDrives": "true"}, files=files)
        return r.json()["id"]
