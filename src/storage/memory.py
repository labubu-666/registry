"""In-memory storage backend for Docker Registry"""

from typing import Any

from .base import BaseStorage
from .refs import manifest_blob_digests
from .schema import ManifestData


class MemoryStorage(BaseStorage):
    """In-memory storage backend.

    Stores all data in RAM. Data is lost when the server restarts.
    Suitable for testing and development.
    """

    def __init__(self):
        """Initialize memory storage with empty data structures"""
        self.manifests: dict[str, dict[str, Any]] = {}
        self.blobs: dict[str, bytes] = {}
        self.repositories: set[str] = set()

    def put_manifest(
        self, name: str, reference: str, manifest_data: ManifestData
    ) -> None:
        """Store a manifest in memory."""
        key = f"{name}:{reference}"
        self.manifests[key] = manifest_data.model_dump()

    def get_manifest(self, name: str, reference: str) -> dict[str, Any] | None:
        """Retrieve a manifest from memory."""
        key = f"{name}:{reference}"
        return self.manifests.get(key)

    def manifest_exists(self, name: str, reference: str) -> bool:
        """Check if a manifest exists in memory."""
        key = f"{name}:{reference}"
        return key in self.manifests

    def delete_manifest(self, name: str, reference: str) -> None:
        """Delete a manifest from memory."""
        key = f"{name}:{reference}"
        if key in self.manifests:
            del self.manifests[key]

    def list_tags(self, name: str) -> list[str]:
        """List all tags for a repository."""
        tags: set[str] = set()
        prefix = f"{name}:"

        for key in self.manifests.keys():
            if key.startswith(prefix):
                ref = key[len(prefix) :]
                # Only include tags, not digest references
                if not ref.startswith("sha256:"):
                    tags.add(ref)

        return list(tags)

    def put_blob(self, digest: str, data: bytes) -> None:
        """Store a blob in memory."""
        self.blobs[digest] = data

    def get_blob(self, digest: str) -> bytes | None:
        """Retrieve a blob from memory."""
        return self.blobs.get(digest)

    def blob_exists(self, digest: str) -> bool:
        """Check if a blob exists in memory."""
        return digest in self.blobs

    def delete_blob(self, digest: str) -> None:
        """Delete a blob from memory."""
        if digest in self.blobs:
            del self.blobs[digest]

    def add_repository(self, name: str) -> None:
        """Register a repository in memory."""
        self.repositories.add(name)

    def list_repositories(self) -> list[str]:
        """List all registered repositories."""
        return list(self.repositories)

    def delete_repository(self, name: str) -> None:
        """Delete a repository from memory."""
        # Remove repository from list
        self.repositories.discard(name)
        # Remove all manifests for this repository
        keys_to_delete = [
            key for key in self.manifests.keys() if key.startswith(f"{name}:")
        ]
        for key in keys_to_delete:
            del self.manifests[key]

    def get_all_manifests_for_repo(self, name: str) -> list[dict[str, Any]]:
        """Get all manifests for a repository."""
        manifests: list[dict[str, Any]] = []
        prefix = f"{name}:"
        for key, manifest_data in self.manifests.items():
            if key.startswith(prefix):
                manifests.append(manifest_data)
        return manifests

    def get_referenced_blobs(self) -> set[str]:
        """Get all blob digests that are currently referenced by any manifest."""
        referenced: set[str] = set()
        for manifest_data in self.manifests.values():
            if isinstance(manifest_data.get("manifest"), dict):
                referenced |= manifest_blob_digests(manifest_data["manifest"])
        return referenced
