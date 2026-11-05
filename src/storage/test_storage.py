"""Tests shared by every storage backend (memory and file)."""

import json

import pytest

from src.storage.base import BaseStorage
from src.storage.file import FileStorage
from src.storage.memory import MemoryStorage
from src.storage.schema import ManifestData

MANIFEST_V2 = "application/vnd.docker.distribution.manifest.v2+json"


def make_manifest(manifest: dict, digest: str = "sha256:m") -> ManifestData:
    """Build a ManifestData with the given manifest JSON."""
    return ManifestData(
        manifest=manifest, content_type=MANIFEST_V2, body=b"body", digest=digest
    )


@pytest.fixture(params=["memory", "file"])
def storage(request, tmp_path) -> BaseStorage:
    """Provide each storage backend in turn, starting empty."""
    if request.param == "memory":
        return MemoryStorage()
    return FileStorage(data_dir=str(tmp_path / "data"))


class TestManifests:
    """Manifest operations shared by all backends."""

    def test_put_and_get_manifest(self, storage):
        """Test storing and retrieving a manifest."""
        # Arrange
        manifest_data = make_manifest({"key": "value"}, digest="sha256:abc123")

        # Act
        storage.put_manifest("alpine", "3.22.4", manifest_data)
        result = storage.get_manifest("alpine", "3.22.4")

        # Assert
        assert result == manifest_data.model_dump()

    def test_get_manifest_not_found(self, storage):
        """Test retrieving a non-existent manifest returns None."""
        # Act
        result = storage.get_manifest("nonexistent", "1.0.0")

        # Assert
        assert result is None

    def test_manifest_exists(self, storage):
        """Test checking if a manifest exists."""
        # Arrange
        storage.put_manifest("alpine", "3.22.4", make_manifest({"key": "value"}))

        # Act
        exists = storage.manifest_exists("alpine", "3.22.4")
        not_exists = storage.manifest_exists("alpine", "1.0.0")

        # Assert
        assert exists is True
        assert not_exists is False

    def test_delete_manifest(self, storage):
        """Test deleting a manifest."""
        # Arrange
        storage.put_manifest("alpine", "3.22.4", make_manifest({"key": "value"}))

        # Act
        storage.delete_manifest("alpine", "3.22.4")

        # Assert
        assert storage.get_manifest("alpine", "3.22.4") is None

    def test_delete_nonexistent_manifest(self, storage):
        """Test deleting a non-existent manifest does not raise an error."""
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
        manifest_data = make_manifest({"name": name})

        # Act
        storage.put_manifest(name, reference, manifest_data)
        result = storage.get_manifest(name, reference)

        # Assert
        assert result == manifest_data.model_dump()

    def test_manifest_reference_with_slashes(self, storage):
        """Test that a reference containing slashes is stored and found again."""
        # Arrange
        manifest_data = make_manifest({"key": "value"})
        reference = "sha256:abc/123/def"

        # Act
        storage.put_manifest("alpine", reference, manifest_data)
        result = storage.get_manifest("alpine", reference)

        # Assert
        assert result == manifest_data.model_dump()


class TestTags:
    """Tag listing shared by all backends."""

    def test_list_tags_empty(self, storage):
        """Test listing tags for a non-existent repository."""
        # Act
        tags = storage.list_tags("alpine")

        # Assert
        assert tags == []

    @pytest.mark.parametrize(
        "references,expected",
        [
            pytest.param(["3.22.4"], {"3.22.4"}, id="single"),
            pytest.param(
                ["3.22.4", "3.21.0", "latest"],
                {"3.22.4", "3.21.0", "latest"},
                id="multiple",
            ),
            pytest.param(
                ["3.22.4", "sha256:abc123", "sha256:def456"],
                {"3.22.4"},
                id="excludes-digests",
            ),
        ],
    )
    def test_list_tags(self, storage, references, expected):
        """Test that list_tags returns tags but not digest references."""
        # Arrange
        for reference in references:
            storage.put_manifest("alpine", reference, make_manifest({}))

        # Act
        tags = storage.list_tags("alpine")

        # Assert
        assert set(tags) == expected

    def test_list_tags_only_for_requested_repository(self, storage):
        """Test that list_tags only returns tags for the specified repository."""
        # Arrange
        storage.put_manifest("alpine", "3.22.4", make_manifest({}))
        storage.put_manifest("ubuntu", "22.04", make_manifest({}))

        # Act
        alpine_tags = storage.list_tags("alpine")
        ubuntu_tags = storage.list_tags("ubuntu")

        # Assert
        assert alpine_tags == ["3.22.4"]
        assert ubuntu_tags == ["22.04"]


class TestBlobs:
    """Blob operations shared by all backends."""

    def test_put_and_get_blob(self, storage):
        """Test storing and retrieving a blob."""
        # Arrange
        blob_data = b"blob content here"

        # Act
        storage.put_blob("sha256:abc123", blob_data)
        result = storage.get_blob("sha256:abc123")

        # Assert
        assert result == blob_data

    def test_get_blob_not_found(self, storage):
        """Test retrieving a non-existent blob returns None."""
        # Act
        result = storage.get_blob("sha256:nonexistent")

        # Assert
        assert result is None

    def test_blob_exists(self, storage):
        """Test checking if a blob exists."""
        # Arrange
        storage.put_blob("sha256:abc123", b"blob data")

        # Act
        exists = storage.blob_exists("sha256:abc123")
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
        """Test storing and retrieving multiple blobs, including empty ones."""
        # Act
        storage.put_blob(digest, data)
        result = storage.get_blob(digest)

        # Assert
        assert result == data

    def test_put_blob_overwrite(self, storage):
        """Test that putting a blob with an existing digest overwrites it."""
        # Arrange
        storage.put_blob("sha256:abc123", b"old content")

        # Act
        storage.put_blob("sha256:abc123", b"new content")
        result = storage.get_blob("sha256:abc123")

        # Assert
        assert result == b"new content"

    def test_delete_blob(self, storage):
        """Test deleting a blob removes it."""
        # Arrange
        storage.put_blob("sha256:abc123", b"blob data")

        # Act
        storage.delete_blob("sha256:abc123")

        # Assert
        assert storage.blob_exists("sha256:abc123") is False
        assert storage.get_blob("sha256:abc123") is None

    def test_delete_nonexistent_blob(self, storage):
        """Test deleting a non-existent blob does not raise an error."""
        # Act & Assert - should not raise
        storage.delete_blob("sha256:nonexistent")


class TestRepositories:
    """Repository operations shared by all backends."""

    def test_add_repository(self, storage):
        """Test adding a repository."""
        # Act
        storage.add_repository("alpine")

        # Assert
        assert "alpine" in storage.list_repositories()

    def test_list_repositories_empty(self, storage):
        """Test listing repositories when none exist."""
        # Act
        repos = storage.list_repositories()

        # Assert
        assert repos == []

    def test_add_duplicate_repository(self, storage):
        """Test that adding a duplicate repository does not create duplicates."""
        # Arrange
        storage.add_repository("alpine")

        # Act
        storage.add_repository("alpine")
        repos = storage.list_repositories()

        # Assert
        assert repos.count("alpine") == 1

    @pytest.mark.parametrize(
        "name", ["alpine", "ubuntu", "python", "nginx", "postgres"]
    )
    def test_add_multiple_repositories(self, storage, name):
        """Test adding various repositories."""
        # Act
        storage.add_repository(name)

        # Assert
        assert name in storage.list_repositories()

    def test_delete_repository_removes_it_and_its_manifests(self, storage):
        """Test deleting a repository removes it and its manifests only."""
        # Arrange
        storage.add_repository("alpine")
        storage.add_repository("ubuntu")
        storage.put_manifest("alpine", "3.22.4", make_manifest({}))
        storage.put_manifest("ubuntu", "22.04", make_manifest({}))

        # Act
        storage.delete_repository("alpine")

        # Assert
        assert "alpine" not in storage.list_repositories()
        assert storage.manifest_exists("alpine", "3.22.4") is False
        assert storage.get_all_manifests_for_repo("alpine") == []
        assert "ubuntu" in storage.list_repositories()
        assert storage.manifest_exists("ubuntu", "22.04") is True

    def test_get_all_manifests_for_repo(self, storage):
        """Test that only the requested repository's manifests are returned."""
        # Arrange
        storage.put_manifest("alpine", "3.22.4", make_manifest({"a": 1}))
        storage.put_manifest("alpine", "latest", make_manifest({"a": 1}))
        storage.put_manifest("ubuntu", "22.04", make_manifest({"u": 1}))

        # Act
        manifests = storage.get_all_manifests_for_repo("alpine")

        # Assert
        assert len(manifests) == 2
        assert all(m["manifest"] == {"a": 1} for m in manifests)


class TestReferencedBlobs:
    """Tests for get_referenced_blobs shared by all backends."""

    def test_get_referenced_blobs(self, storage):
        """Test that config and layer digests are extracted from a manifest."""
        # Arrange
        manifest = {
            "config": {"digest": "sha256:cfg"},
            "layers": [{"digest": "sha256:l1"}, {"digest": "sha256:l2"}],
        }
        storage.put_manifest("alpine", "3.22.4", make_manifest(manifest))

        # Act
        referenced = storage.get_referenced_blobs()

        # Assert
        assert referenced == {"sha256:cfg", "sha256:l1", "sha256:l2"}

    def test_get_referenced_blobs_empty(self, storage):
        """Test that no manifests yield no referenced blobs."""
        # Act
        referenced = storage.get_referenced_blobs()

        # Assert
        assert referenced == set()


class TestFileStoragePersistence:
    """Tests that only apply to the on-disk FileStorage backend."""

    def test_manifest_persists_across_instances(self, tmp_path):
        """Test that a manifest survives creating a new storage instance."""
        # Arrange
        data_dir = str(tmp_path / "data")
        manifest_data = make_manifest({"key": "value"})
        FileStorage(data_dir=data_dir).put_manifest("alpine", "3.22.4", manifest_data)

        # Act
        result = FileStorage(data_dir=data_dir).get_manifest("alpine", "3.22.4")

        # Assert
        assert result == manifest_data.model_dump()

    def test_repositories_persist_across_instances(self, tmp_path):
        """Test that repositories survive creating a new storage instance."""
        # Arrange
        data_dir = str(tmp_path / "data")
        FileStorage(data_dir=data_dir).add_repository("alpine")

        # Act
        repos = FileStorage(data_dir=data_dir).list_repositories()

        # Assert
        assert repos == ["alpine"]

    def test_blob_persists_across_instances(self, tmp_path):
        """Test that a blob survives creating a new storage instance."""
        # Arrange
        data_dir = str(tmp_path / "data")
        FileStorage(data_dir=data_dir).put_blob("sha256:abc123", b"blob data")

        # Act
        result = FileStorage(data_dir=data_dir).get_blob("sha256:abc123")

        # Assert
        assert result == b"blob data"

    def test_creates_required_directories(self, tmp_path):
        """Test that storage creates the manifests and blobs directories."""
        # Arrange
        data_dir = tmp_path / "data"

        # Act
        FileStorage(data_dir=str(data_dir))

        # Assert
        assert (data_dir / "manifests").is_dir()
        assert (data_dir / "blobs").is_dir()

    def test_manifest_file_layout_is_json(self, tmp_path):
        """Test that a manifest is written as JSON under manifests/<repo>/<ref>.json."""
        # Arrange
        data_dir = tmp_path / "data"
        storage = FileStorage(data_dir=str(data_dir))

        # Act
        storage.put_manifest("alpine", "3.22.4", make_manifest({"key": "value"}))

        # Assert
        loaded = json.loads(
            (data_dir / "manifests" / "alpine" / "3.22.4.json").read_text()
        )
        assert loaded["manifest"] == {"key": "value"}
        assert loaded["digest"] == "sha256:m"

    def test_blob_file_layout_is_raw_bytes(self, tmp_path):
        """Test that a blob is written as raw bytes under blobs/<digest>."""
        # Arrange
        data_dir = tmp_path / "data"
        storage = FileStorage(data_dir=str(data_dir))

        # Act
        storage.put_blob("sha256:abc123", b"test blob content")

        # Assert
        assert (
            data_dir / "blobs" / "sha256:abc123"
        ).read_bytes() == b"test blob content"

    def test_repositories_file_is_json(self, tmp_path):
        """Test that the repositories list is stored as a JSON array."""
        # Arrange
        data_dir = tmp_path / "data"
        storage = FileStorage(data_dir=str(data_dir))

        # Act
        storage.add_repository("alpine")
        storage.add_repository("ubuntu")

        # Assert
        repos = json.loads((data_dir / "repositories.json").read_text())
        assert set(repos) == {"alpine", "ubuntu"}
