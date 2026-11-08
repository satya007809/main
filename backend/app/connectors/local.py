"""Local-folder connector for development and automated tests. Disabled unless BID_ALLOW_LOCAL_CONNECTOR=true."""
from __future__ import annotations

import mimetypes
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

from .base import CloudConnector, ConnectorError, RemoteFile


class LocalFolderConnector(CloudConnector):
    provider = "local"

    def __init__(self, root: str):
        self.root = Path(root).resolve()

    def _resolve(self, rel: str) -> Path:
        p = (self.root / rel).resolve()
        if self.root not in p.parents and p != self.root:
            raise ConnectorError("Path escapes the local connector root")
        return p

    def parse_link(self, link: str) -> str:
        rel = link.removeprefix("local://").strip("/")
        if not self._resolve(rel).is_dir():
            raise ConnectorError("Local folder not found")
        return rel

    def folder_name(self, folder_id: str) -> str:
        return self._resolve(folder_id).name

    def walk(self, folder_id: str) -> Iterator[RemoteFile]:
        base = self._resolve(folder_id)
        for p in sorted(base.rglob("*")):
            if p.is_file():
                rel_dir = str(p.parent.relative_to(base)).replace("\\", "/")
                yield RemoteFile(
                    id=str(p.relative_to(self.root)), name=p.name, path="" if rel_dir == "." else rel_dir,
                    mime_type=mimetypes.guess_type(p.name)[0] or "", size=p.stat().st_size,
                    modified_time=datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat())

    def download(self, f: RemoteFile) -> tuple[bytes, str]:
        return self._resolve(f.id).read_bytes(), f.name

    def upload(self, folder_id: str, filename: str, data: bytes, mime_type: str) -> str:
        p = self._resolve(folder_id) / filename
        p.write_bytes(data)
        return str(p.relative_to(self.root))
