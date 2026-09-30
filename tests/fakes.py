"""Test doubles for infrastructure services."""
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO

from app.storage.s3 import ObjectNotFoundError, StorageError


class InMemoryStorage:
    """Implements app.storage.base.Storage in memory.

    `fail_uploads_after` makes every upload after that many succeed raise StorageError.
    """

    def __init__(self, fail_uploads_after: int | None = None):
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.fail_uploads_after = fail_uploads_after

    def upload(self, key: str, fileobj: BinaryIO, content_type: str) -> None:
        if self.fail_uploads_after is not None and len(self.objects) >= self.fail_uploads_after:
            raise StorageError(f"Storage upload failed for {key}")
        self.objects[key] = (fileobj.read(), content_type)

    def download(self, key: str, destination: Path) -> None:
        if key not in self.objects:
            raise ObjectNotFoundError(f"Object not found: {key}")
        destination.write_bytes(self.objects[key][0])

    def stream(self, key: str, start: int, end: int) -> Iterator[bytes]:
        if key not in self.objects:
            raise ObjectNotFoundError(f"Object not found: {key}")
        return iter([self.objects[key][0][start:end + 1]])

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)
