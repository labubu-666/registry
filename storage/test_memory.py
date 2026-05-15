"""Tests for in-memory storage backend"""

import pytest
from src.storage.schema import ManifestData
from .memory import MemoryStorage


@pytest.fixture
def storage():
    """Provide a fresh MemoryStorage instance for each test."""
    return MemoryStorage()


class TestMemoryStorageManifests:
    """Tests for manifest operations in MemoryStorage."""

    def test_put_and_get_manifest(self, storage):
        """Test storing and retrieving a manifest."""
        # Arrange
        manifest_data = {
            "manifest": {"key": "value"},
            "content_type": "application/vnd.docker.distribution.manifest.v2+json",
            "body": b"manifest body",
            "digest": "sha256:abc123",
        }

        # Act
        storage.put_manifest("alpine", "3.22.4", manifest_data)
        result = storage.get_manifest("alpine", "3.22.4")

        # Assert
        assert result == manifest_data

    def test_get_manifest_not_found(self, storage):
        """Test retrieving a non-existent manifest returns None."""
        # Arrange & Act
        result = storage.get_manifest("nonexistent", "1.0.0")

        # Assert
        assert result is None

    def test_manifest_exists(self, storage):
        """Test checking if manifest exists."""
        # Arrange
        manifest_data = {"manifest": {"key": "value"}}

        # Act
        storage.put_manifest("alpine", "3.22.4", manifest_data)
        exists = storage.manifest_exists("alpine", "3.22.4")
        not_exists = storage.manifest_exists("alpine", "1.0.0")

        # Assert
        assert exists is True
        assert not_exists is False

    def test_delete_manifest(self, storage):
        """Test deleting a manifest."""
        # Arrange
        manifest_data = {"manifest": {"key": "value"}}
        storage.put_manifest("alpine", "3.22.4", manifest_data)

        # Act
        storage.delete_manifest("alpine", "3.22.4")
        result = storage.get_manifest("alpine", "3.22.4")

        # Assert
        assert result is None

    def test_delete_nonexistent_manifest(self, storage):
        """Test deleting a non-existent manifest does not raise error."""
        # Act & Assert - should not raise
        storage.delete_manifest("nonexistent", "1.0.0")

    @pytest.mark.parametrize(
        "name,reference",
        [
            ("alpine", "3.22.4"),
            ("ubuntu", "22.04"),
            ("python", "3.11-slim"),
        ],
    )
    def test_put_and_get_multiple_manifests(self, storage, name, reference):
        """Test storing and retrieving multiple manifests."""
        # Arrange
        manifest_data = {"manifest": {"key": "value"}, "name": name}

        # Act
        storage.put_manifest(name, reference, manifest_data)
        result = storage.get_manifest(name, reference)

        # Assert
        assert result == manifest_data


class TestMemoryStorageTags:
    """Tests for tag operations in MemoryStorage."""

    def test_list_tags_empty(self, storage):
        """Test listing tags for non-existent repository."""
        # Act
        tags = storage.list_tags("alpine")

        # Assert
        assert tags == []

    def test_list_tags_single(self, storage):
        """Test listing a single tag."""
        # Arrange
        storage.put_manifest("alpine", "3.22.4", {"manifest": {}})

        # Act
        tags = storage.list_tags("alpine")

        # Assert
        assert tags == ["3.22.4"]

    def test_list_tags_multiple(self, storage):
        """Test listing multiple tags."""
        # Arrange
        storage.put_manifest("alpine", "3.22.4", {"manifest": {}})
        storage.put_manifest("alpine", "3.21.0", {"manifest": {}})
        storage.put_manifest("alpine", "latest", {"manifest": {}})

        # Act
        tags = storage.list_tags("alpine")

        # Assert
        assert set(tags) == {"3.22.4", "3.21.0", "latest"}

    def test_list_tags_excludes_digests(self, storage):
        """Test that list_tags excludes digest references."""
        # Arrange
        storage.put_manifest("alpine", "3.22.4", {"manifest": {}})
        storage.put_manifest("alpine", "sha256:abc123", {"manifest": {}})
        storage.put_manifest("alpine", "sha256:def456", {"manifest": {}})

        # Act
        tags = storage.list_tags("alpine")

        # Assert
        assert tags == ["3.22.4"]

    def test_list_tags_different_repositories(self, storage):
        """Test that list_tags only returns tags for specified repository."""
        # Arrange
        storage.put_manifest("alpine", "3.22.4", {"manifest": {}})
        storage.put_manifest("ubuntu", "22.04", {"manifest": {}})

        # Act
        alpine_tags = storage.list_tags("alpine")
        ubuntu_tags = storage.list_tags("ubuntu")

        # Assert
        assert alpine_tags == ["3.22.4"]
        assert ubuntu_tags == ["22.04"]


class TestMemoryStorageBlobs:
    """Tests for blob operations in MemoryStorage."""

    def test_put_and_get_blob(self, storage):
        """Test storing and retrieving a blob."""
        # Arrange
        blob_data = b"blob content here"
        digest = "sha256:abc123"

        # Act
        storage.put_blob(digest, blob_data)
        result = storage.get_blob(digest)

        # Assert
        assert result == blob_data

    def test_get_blob_not_found(self, storage):
        """Test retrieving a non-existent blob returns None."""
        # Act
        result = storage.get_blob("sha256:nonexistent")

        # Assert
        assert result is None

    def test_blob_exists(self, storage):
        """Test checking if blob exists."""
        # Arrange
        digest = "sha256:abc123"
        storage.put_blob(digest, b"blob data")

        # Act
        exists = storage.blob_exists(digest)
        not_exists = storage.blob_exists("sha256:nonexistent")

        # Assert
        assert exists is True
        assert not_exists is False

    @pytest.mark.parametrize(
        "digest,data",
        [
            ("sha256:abc123", b"content1"),
            ("sha256:def456", b"content2"),
            ("sha256:ghi789", b""),
        ],
    )
    def test_put_and_get_multiple_blobs(self, storage, digest, data):
        """Test storing and retrieving multiple blobs."""
        # Act
        storage.put_blob(digest, data)
        result = storage.get_blob(digest)

        # Assert
        assert result == data

    def test_put_blob_overwrite(self, storage):
        """Test that putting a blob with existing digest overwrites it."""
        # Arrange
        digest = "sha256:abc123"
        storage.put_blob(digest, b"old content")

        # Act
        storage.put_blob(digest, b"new content")
        result = storage.get_blob(digest)

        # Assert
        assert result == b"new content"


class TestMemoryStorageRepositories:
    """Tests for repository operations in MemoryStorage."""

    def test_add_repository(self, storage):
        """Test adding a repository."""
        # Act
        storage.add_repository("alpine")
        repos = storage.list_repositories()

        # Assert
        assert "alpine" in repos

    def test_list_repositories_empty(self, storage):
        """Test listing repositories when none exist."""
        # Act
        repos = storage.list_repositories()

        # Assert
        assert repos == []

    def test_list_repositories_multiple(self, storage):
        """Test listing multiple repositories."""
        # Arrange
        storage.add_repository("alpine")
        storage.add_repository("ubuntu")
        storage.add_repository("python")

        # Act
        repos = storage.list_repositories()

        # Assert
        assert set(repos) == {"alpine", "ubuntu", "python"}

    def test_add_duplicate_repository(self, storage):
        """Test that adding duplicate repository doesn't create duplicates."""
        # Arrange
        storage.add_repository("alpine")

        # Act
        storage.add_repository("alpine")
        repos = storage.list_repositories()

        # Assert
        assert repos.count("alpine") == 1

    @pytest.mark.parametrize(
        "name",
        [
            "alpine",
            "ubuntu",
            "python",
            "nginx",
            "postgres",
        ],
    )
    def test_add_multiple_repositories(self, storage, name):
        """Test adding various repositories."""
        # Act
        storage.add_repository(name)
        repos = storage.list_repositories()

        # Assert
        assert name in repos


class TestMemoryStorageIntegration:
    """Integration tests for MemoryStorage."""

    def test_complete_workflow(self, storage):
        """Test a complete workflow with manifests, blobs, and repositories."""
        # Arrange
        manifest_data = {
            "manifest": {"config": {"digest": "sha256:blob1"}},
            "content_type": "application/vnd.docker.distribution.manifest.v2+json",
            "body": b"manifest",
            "digest": "sha256:manifest1",
        }
        blob_data = b"layer content"

        # Act
        storage.add_repository("alpine")
        storage.put_manifest("alpine", "3.22.4", manifest_data)
        storage.put_blob("sha256:blob1", blob_data)

        # Assert
        assert storage.manifest_exists("alpine", "3.22.4")
        assert storage.blob_exists("sha256:blob1")
        assert "alpine" in storage.list_repositories()
        assert "3.22.4" in storage.list_tags("alpine")

    def test_independent_storage_instances(self):
        """Test that storage instances don't share data."""
        # Arrange
        storage1 = MemoryStorage()
        storage2 = MemoryStorage()

        # Act
        storage1.add_repository("alpine")
        storage1.put_manifest(
            "alpine",
            "3.22.4",
            ManifestData(manifest={}, body=b"", digest="sha256:abc"),
        )

        # Assert
        assert "alpine" not in storage2.list_repositories()
        assert storage2.get_manifest("alpine", "3.22.4") is None
