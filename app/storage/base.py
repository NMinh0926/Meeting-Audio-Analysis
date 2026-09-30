"""Storage interface the services depend on (S3Storage in production, an in-memory fake in tests)."""
from pathlib import Path
from typing import BinaryIO, Protocol


class Storage(Protocol):
    def upload(self, key: str, fileobj: BinaryIO, content_type: str) -> None: ...

    def download(self, key: str, destination: Path) -> None: ...

    def delete(self, key: str) -> None: ...
