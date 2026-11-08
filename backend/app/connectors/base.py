"""Cloud-folder connector interface. Add a provider by implementing CloudConnector and registering it."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field


class ConnectorError(Exception):
    """Raised for provider errors that should be reported to the user (permission denied, bad link...)."""


@dataclass
class RemoteFile:
    id: str
    name: str
    path: str  # folder path relative to the linked root, e.g. "Photos/Spot"
    mime_type: str = ""
    size: int = 0
    modified_time: str = ""
    checksum: str = ""
    download_hint: dict = field(default_factory=dict)  # provider-specific (export mime, download url...)

    @property
    def full_path(self) -> str:
        return f"{self.path}/{self.name}" if self.path else self.name


class CloudConnector(ABC):
    provider: str = ""

    @abstractmethod
    def parse_link(self, link: str) -> str:
        """Return the provider folder id for a pasted share link (raise ConnectorError if invalid)."""

    @abstractmethod
    def folder_name(self, folder_id: str) -> str: ...

    @abstractmethod
    def walk(self, folder_id: str) -> Iterator[RemoteFile]:
        """Yield every file under the folder, recursively, including nested sub-folders."""

    @abstractmethod
    def download(self, f: RemoteFile) -> tuple[bytes, str]:
        """Return (content, effective filename). Native cloud docs are exported to Office formats."""

    @abstractmethod
    def upload(self, folder_id: str, filename: str, data: bytes, mime_type: str) -> str: ...
