"""File-based storage backend for Docker Registry"""

import base64
import json
from pathlib import Path
from typing import Any

from .base import BaseStorage
from .refs import manifest_blob_digests
from .schema import ManifestData


class FileStorage(BaseStorage):
    """File-based persistent storage backend.

    Stores manifests and blobs on disk. Data persists across server restarts.
    Suitable for production use with single-instance deployments.

    Directory structure:
        data/
        ├── manifests/
        │   └── {repository}/
        │       ├── {reference}.json
        │       └── {digest}.json
        ├── blobs/
        │   └── {digest}
        └── repositories.json
    """

    def __init__(self, data_dir: str = "data"):
        """Initialize file storage with a data directory.

        Args:
            data_dir: Root directory for storing data (default: "data")
        """
        self.data_dir = Path(data_dir)
        self.manifests_dir = self.data_dir / "manifests"
        self.blobs_dir = self.data_dir / "blobs"

        # Create directories if they don't exist
        self.manifests_dir.mkdir(parents=True, exist_ok=True)
        self.blobs_dir.mkdir(parents=True, exist_ok=True)

    def _get_manifest_path(self, name: str, reference: str) -> Path:
        """Get the file path for a manifest."""
        repo_dir = self.manifests_dir / name
        repo_dir.mkdir(parents=True, exist_ok=True)
        # Sanitize the reference for use as a filename
        safe_ref = reference.replace("/", "_")
        return repo_dir / f"{safe_ref}.json"

    def _get_blob_path(self, digest: str) -> Path:
        """Get the file path for a blob."""
        return self.blobs_dir / digest

    def _get_repositories_path(self) -> Path:
        """Get the file path for the repositories list."""
        return self.data_dir / "repositories.json"

    def _load_repositories(self) -> set[str]:
        """Load repositories from disk."""
        repos_file = self._get_repositories_path()
        if repos_file.exists():
            try:
                with open(repos_file) as f:
                    return set(json.load(f))
            except OSError, json.JSONDecodeError:
                return set()
        return set()

    def _save_repositories(self, repositories: set[str]) -> None:
        """Save repositories to disk."""
        repos_file = self._get_repositories_path()
        with open(repos_file, "w") as f:
            json.dump(list(repositories), f, indent=2)

    def put_manifest(
        self, name: str, reference: str, manifest_data: ManifestData
    ) -> None:
        """Store a manifest to disk."""
        # Handle binary data in manifest_data
        # ManifestData.body is always bytes, so it is always base64-encoded here
        serializable_data: dict[str, Any] = manifest_data.model_dump()
        serializable_data["body"] = base64.b64encode(serializable_data["body"]).decode(
            "utf-8"
        )

        manifest_path = self._get_manifest_path(name, reference)
        with open(manifest_path, "w") as f:
            json.dump(serializable_data, f, indent=2)

    def get_manifest(self, name: str, reference: str) -> dict[str, Any] | None:
        """Retrieve a manifest from disk."""
        manifest_path = self._get_manifest_path(name, reference)
        if manifest_path.exists():
            try:
                with open(manifest_path) as f:
                    data = json.load(f)
                    # Decode body back to bytes if present
                    if "body" in data and isinstance(data["body"], str):
                        data["body"] = base64.b64decode(data["body"])
                    return data
            except OSError, json.JSONDecodeError:
                return None
        return None

    def manifest_exists(self, name: str, reference: str) -> bool:
        """Check if a manifest exists on disk."""
        manifest_path = self._get_manifest_path(name, reference)
        return manifest_path.exists()

    def delete_manifest(self, name: str, reference: str) -> None:
        """Delete a manifest from disk."""
        manifest_path = self._get_manifest_path(name, reference)
        if manifest_path.exists():
            manifest_path.unlink()

    def list_tags(self, name: str) -> list[str]:
        """List all tags for a repository."""
        tags: set[str] = set()
        repo_dir = self.manifests_dir / name

        if repo_dir.exists():
            for file_path in repo_dir.glob("*.json"):
                reference = file_path.stem
                # Unsanitize the reference
                reference = reference.replace("_", "/")
                # Only include tags, not digest references
                if not reference.startswith("sha256:"):
                    tags.add(reference)

        return list(tags)

    def put_blob(self, digest: str, data: bytes) -> None:
        """Store a blob to disk."""
        blob_path = self._get_blob_path(digest)
        with open(blob_path, "wb") as f:
            f.write(data)

    def get_blob(self, digest: str) -> bytes | None:
        """Retrieve a blob from disk."""
        blob_path = self._get_blob_path(digest)
        if blob_path.exists():
            try:
                with open(blob_path, "rb") as f:
                    return f.read()
            except OSError:
                return None
        return None

    def blob_exists(self, digest: str) -> bool:
        """Check if a blob exists on disk."""
        blob_path = self._get_blob_path(digest)
        return blob_path.exists()

    def delete_blob(self, digest: str) -> None:
        """Delete a blob from disk."""
        blob_path = self._get_blob_path(digest)
        if blob_path.exists():
            blob_path.unlink()

    def add_repository(self, name: str) -> None:
        """Register a repository."""
        repositories = self._load_repositories()
        repositories.add(name)
        self._save_repositories(repositories)

    def list_repositories(self) -> list[str]:
        """List all registered repositories."""
        return list(self._load_repositories())

    def delete_repository(self, name: str) -> None:
        """Delete a repository from disk."""
        # Remove repository from repositories list
        repositories = self._load_repositories()
        repositories.discard(name)
        self._save_repositories(repositories)

        # Remove repository directory
        repo_dir = self.manifests_dir / name
        if repo_dir.exists():
            import shutil

            shutil.rmtree(repo_dir)

    def get_all_manifests_for_repo(self, name: str) -> list[dict[str, Any]]:
        """Get all manifests for a repository."""
        manifests: list[dict[str, Any]] = []
        repo_dir = self.manifests_dir / name

        if repo_dir.exists():
            for file_path in repo_dir.glob("*.json"):
                try:
                    with open(file_path) as f:
                        data = json.load(f)
                        # Decode body back to bytes if present
                        if "body" in data and isinstance(data["body"], str):
                            data["body"] = base64.b64decode(data["body"])
                        manifests.append(data)
                except OSError, json.JSONDecodeError:
                    pass

        return manifests

    def get_referenced_blobs(self) -> set[str]:
        """Get all blob digests that are currently referenced by any manifest."""
        referenced: set[str] = set()
        if not self.manifests_dir.exists():
            return referenced

        for repo_dir in self.manifests_dir.iterdir():
            if not repo_dir.is_dir():
                continue
            for file_path in repo_dir.glob("*.json"):
                try:
                    with open(file_path) as f:
                        data = json.load(f)
                except OSError, json.JSONDecodeError:
                    continue
                if isinstance(data.get("manifest"), dict):
                    referenced |= manifest_blob_digests(data["manifest"])
        return referenced
