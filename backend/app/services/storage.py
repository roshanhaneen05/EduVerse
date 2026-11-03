import io
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO, Optional

from app.config import get_settings

settings = get_settings()


class BaseStorageProvider(ABC):
    """Abstract Base Class for EduVerse File Storage Providers."""

    @abstractmethod
    def save_file(self, storage_key: str, content: bytes) -> str:
        """Persist file content under the generated unique storage key. Returns the storage key."""
        pass

    @abstractmethod
    def get_file_bytes(self, storage_key: str) -> bytes:
        """Retrieve full file content as bytes."""
        pass

    @abstractmethod
    def get_file_stream(self, storage_key: str) -> BinaryIO:
        """Retrieve a readable binary stream for the stored file."""
        pass

    @abstractmethod
    def get_file_path(self, storage_key: str) -> Optional[Path]:
        """Return the physical filesystem Path if local, else None (e.g. for cloud objects)."""
        pass

    @abstractmethod
    def delete_file(self, storage_key: str) -> bool:
        """Delete stored file by storage key. Returns True if deleted, False if not found."""
        pass

    @abstractmethod
    def file_exists(self, storage_key: str) -> bool:
        """Check whether the file exists in storage."""
        pass


class LocalStorageProvider(BaseStorageProvider):
    """
    Local filesystem storage provider for development and Windows environments.
    Stores files strictly inside the configured upload directory outside the public frontend tree.
    Prevents path traversal attacks by validating resolved filesystem boundaries.
    """

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir.resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, storage_key: str) -> Path:
        """Sanitize storage key and ensure resolved path does not escape base_dir."""
        # Clean any directory separators from storage_key
        clean_name = Path(storage_key).name
        resolved_path = (self.base_dir / clean_name).resolve()

        # Strict path traversal check
        try:
            resolved_path.relative_to(self.base_dir)
        except ValueError:
            raise ValueError(f"Security violation: path traversal detected for key '{storage_key}'.")

        return resolved_path

    def save_file(self, storage_key: str, content: bytes) -> str:
        safe_path = self._resolve_safe_path(storage_key)
        with open(safe_path, "wb") as f:
            f.write(content)
        return storage_key

    def get_file_bytes(self, storage_key: str) -> bytes:
        safe_path = self._resolve_safe_path(storage_key)
        if not safe_path.is_file():
            raise FileNotFoundError(f"Material file not found in storage: {storage_key}")
        with open(safe_path, "rb") as f:
            return f.read()

    def get_file_stream(self, storage_key: str) -> BinaryIO:
        safe_path = self._resolve_safe_path(storage_key)
        if not safe_path.is_file():
            raise FileNotFoundError(f"Material file not found in storage: {storage_key}")
        return open(safe_path, "rb")

    def get_file_path(self, storage_key: str) -> Optional[Path]:
        safe_path = self._resolve_safe_path(storage_key)
        if safe_path.is_file():
            return safe_path
        return None

    def delete_file(self, storage_key: str) -> bool:
        try:
            safe_path = self._resolve_safe_path(storage_key)
            if safe_path.is_file():
                safe_path.unlink()
                return True
        except Exception:
            pass
        return False

    def file_exists(self, storage_key: str) -> bool:
        try:
            safe_path = self._resolve_safe_path(storage_key)
            return safe_path.is_file()
        except Exception:
            return False


class AzureBlobStorageProvider(BaseStorageProvider):
    """
    Azure Blob Storage provider placeholder for production deployment.
    Implements identical interface without requiring API rewriting.
    """

    def __init__(self, connection_string: Optional[str] = None, container_name: str = "learning-materials"):
        self.connection_string = connection_string
        self.container_name = container_name

    def save_file(self, storage_key: str, content: bytes) -> str:
        raise NotImplementedError("Azure Blob Storage will be configured in cloud production phase.")

    def get_file_bytes(self, storage_key: str) -> bytes:
        raise NotImplementedError("Azure Blob Storage will be configured in cloud production phase.")

    def get_file_stream(self, storage_key: str) -> BinaryIO:
        raise NotImplementedError("Azure Blob Storage will be configured in cloud production phase.")

    def get_file_path(self, storage_key: str) -> Optional[Path]:
        return None

    def delete_file(self, storage_key: str) -> bool:
        raise NotImplementedError("Azure Blob Storage will be configured in cloud production phase.")

    def file_exists(self, storage_key: str) -> bool:
        raise NotImplementedError("Azure Blob Storage will be configured in cloud production phase.")


def get_storage_provider() -> BaseStorageProvider:
    """Factory returning the active storage provider based on application configuration."""
    cfg = get_settings()
    if cfg.STORAGE_PROVIDER_TYPE.lower() == "azure_blob":
        return AzureBlobStorageProvider()
    return LocalStorageProvider(cfg.resolved_upload_dir)

