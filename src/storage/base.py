"""Abstract base class for storage backends"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Set
from .schema import ManifestData


class BaseStorage(ABC):
    """Abstract base class for storage backends.

    All storage implementations should inherit from this class and implement
    the abstract methods.
    """

    @abstractmethod
    def put_manifest(
        self, name: str, reference: str, manifest_data: "ManifestData"
    ) -> None:
        """Store a manifest.

        Args:
            name: Repository name (e.g., "alpine")
            reference: Tag or digest (e.g., "3.22.4" or "sha256:abc123...")
            manifest_data: ManifestData
                Expected keys:
                - manifest: The parsed manifest JSON
                - content_type: Content type header
                - body: Raw bytes of the manifest
                - digest: SHA256 digest
        """
        pass

    @abstractmethod
    def get_manifest(self, name: str, reference: str) -> Optional[Dict[str, Any]]:
        """Retrieve a manifest.

        Args:
            name: Repository name
            reference: Tag or digest

        Returns:
            Manifest data dictionary or None if not found
        """
        pass

    @abstractmethod
    def manifest_exists(self, name: str, reference: str) -> bool:
        """Check if a manifest exists.

        Args:
            name: Repository name
            reference: Tag or digest

        Returns:
            True if manifest exists, False otherwise
        """
        pass

    @abstractmethod
    def delete_manifest(self, name: str, reference: str) -> None:
        """Delete a manifest.

        Args:
            name: Repository name
            reference: Tag or digest
        """
        pass

    @abstractmethod
    def list_tags(self, name: str) -> List[str]:
        """List all tags for a repository.

        Args:
            name: Repository name

        Returns:
            List of tag strings (not digest references)
        """
        pass

    @abstractmethod
    def put_blob(self, digest: str, data: bytes) -> None:
        """Store a blob.

        Args:
            digest: SHA256 digest (e.g., "sha256:abc123...")
            data: Raw blob data
        """
        pass

    @abstractmethod
    def get_blob(self, digest: str) -> Optional[bytes]:
        """Retrieve a blob.

        Args:
            digest: SHA256 digest

        Returns:
            Blob data bytes or None if not found
        """
        pass

    @abstractmethod
    def blob_exists(self, digest: str) -> bool:
        """Check if a blob exists.

        Args:
            digest: SHA256 digest

        Returns:
            True if blob exists, False otherwise
        """
        pass

    @abstractmethod
    def delete_blob(self, digest: str) -> None:
        """Delete a blob.

        Args:
            digest: SHA256 digest
        """
        pass

    @abstractmethod
    def add_repository(self, name: str) -> None:
        """Register a repository.

        Args:
            name: Repository name
        """
        pass

    @abstractmethod
    def list_repositories(self) -> List[str]:
        """List all registered repositories.

        Returns:
            List of repository names
        """
        pass

    @abstractmethod
    def delete_repository(self, name: str) -> None:
        """Delete a repository from the registry.

        Args:
            name: Repository name
        """
        pass

    @abstractmethod
    def get_all_manifests_for_repo(self, name: str) -> List[Dict[str, Any]]:
        """Get all manifests for a repository.

        Args:
            name: Repository name

        Returns:
            List of manifest data dictionaries
        """
        pass

    @abstractmethod
    def get_referenced_blobs(self) -> Set[str]:
        """Get all blob digests that are currently referenced by any manifest.

        Returns:
            Set of blob digest strings
        """
        pass
