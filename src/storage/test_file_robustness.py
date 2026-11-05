"""Tests for FileStorage behaviour when files on disk are corrupt or unreadable."""

import json

import pytest

from src.storage.file import FileStorage
from src.storage.schema import ManifestData


@pytest.fixture
def data_dir(tmp_path):
    """Return the data directory used by the storage under test."""
    return tmp_path / "data"


@pytest.fixture
def storage(data_dir) -> FileStorage:
    """Provide a FileStorage rooted at a temporary data directory."""
    return FileStorage(data_dir=str(data_dir))


class TestCorruptRepositoriesFile:
    """Tests for a damaged repositories.json."""

    @pytest.mark.parametrize(
        "content",
        [
            pytest.param("not json", id="garbage"),
            pytest.param('["alpine"', id="truncated"),
        ],
    )
    def test_list_repositories_returns_empty_on_bad_json(
        self, storage, data_dir, content
    ):
        """Test that unparseable repositories.json is treated as an empty list."""
        # Arrange
        (data_dir / "repositories.json").write_text(content)

        # Act
        repos = storage.list_repositories()

        # Assert
        assert repos == []


class TestCorruptManifests:
    """Tests for a damaged manifest file on disk."""

    @pytest.fixture
    def corrupt_manifest(self, data_dir):
        """Write an unparseable manifest file for alpine:3.22.4."""
        path = data_dir / "manifests" / "alpine" / "3.22.4.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not valid json")
        return path

    def test_get_manifest_returns_none(self, storage, corrupt_manifest):
        """Test that a corrupt manifest reads as missing."""
        # Act
        result = storage.get_manifest("alpine", "3.22.4")

        # Assert
        assert result is None

    def test_get_all_manifests_skips_corrupt_entries(self, storage, corrupt_manifest):
        """Test that corrupt manifests are skipped and healthy ones returned."""
        # Arrange
        storage.put_manifest(
            "alpine",
            "latest",
            ManifestData(manifest={}, body=b"", digest="sha256:ok"),
        )

        # Act
        manifests = storage.get_all_manifests_for_repo("alpine")

        # Assert
        assert len(manifests) == 1

    def test_get_referenced_blobs_skips_corrupt_entries(
        self, storage, corrupt_manifest
    ):
        """Test that corrupt manifests do not contribute referenced blobs."""
        # Arrange
        storage.put_manifest(
            "alpine",
            "latest",
            ManifestData(
                manifest={"config": {"digest": "sha256:cfg"}},
                body=b"",
                digest="sha256:ok",
            ),
        )

        # Act
        referenced = storage.get_referenced_blobs()

        # Assert
        assert referenced == {"sha256:cfg"}


class TestUnreadableBlobs:
    """Tests for blob paths that exist but cannot be read as files."""

    def test_get_blob_returns_none_when_path_is_a_directory(self, storage, data_dir):
        """Test that an unreadable blob path reads as missing rather than raising."""
        # Arrange
        (data_dir / "blobs" / "sha256:dir").mkdir()

        # Act
        result = storage.get_blob("sha256:dir")

        # Assert
        assert result is None


class TestHandWrittenFileShapes:
    """Tests for manifest files whose contents don't match what put_manifest writes."""

    @pytest.fixture
    def write_manifest_file(self, data_dir):
        """Write a raw JSON document as the manifest for alpine:<reference>."""

        def _write(reference: str, document: dict) -> None:
            path = data_dir / "manifests" / "alpine" / f"{reference}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(document))

        return _write

    def test_get_manifest_leaves_non_string_body_unchanged(
        self, storage, write_manifest_file
    ):
        """Test that a body that is not a base64 string is returned as stored."""
        # Arrange
        write_manifest_file("3.22.4", {"body": None, "manifest": {}})

        # Act
        result = storage.get_manifest("alpine", "3.22.4")

        # Assert
        assert result == {"body": None, "manifest": {}}

    def test_get_all_manifests_leaves_non_string_body_unchanged(
        self, storage, write_manifest_file
    ):
        """Test that get_all_manifests_for_repo also keeps a non-string body as is."""
        # Arrange
        write_manifest_file("3.22.4", {"body": None, "manifest": {}})

        # Act
        manifests = storage.get_all_manifests_for_repo("alpine")

        # Assert
        assert manifests == [{"body": None, "manifest": {}}]

    def test_get_referenced_blobs_without_manifests_dir_is_empty(
        self, storage, data_dir
    ):
        """Test that referenced blobs are empty when the manifests directory is gone."""
        # Arrange
        (data_dir / "manifests").rmdir()

        # Act
        referenced = storage.get_referenced_blobs()

        # Assert
        assert referenced == set()

    def test_get_referenced_blobs_ignores_stray_files_in_manifests_dir(
        self, storage, data_dir
    ):
        """Test that a file sitting directly in manifests/ is not treated as a repo."""
        # Arrange
        (data_dir / "manifests" / "stray.json").write_text(
            json.dumps({"manifest": {"config": {"digest": "sha256:x"}}})
        )

        # Act
        referenced = storage.get_referenced_blobs()

        # Assert
        assert referenced == set()

    @pytest.mark.parametrize(
        "document",
        [
            pytest.param({"body": "", "digest": "sha256:x"}, id="no-manifest-key"),
            pytest.param({"manifest": "not-a-dict"}, id="manifest-not-dict"),
            pytest.param({"manifest": {"config": "not-a-dict"}}, id="config-not-dict"),
            pytest.param({"manifest": {"config": {"size": 1}}}, id="config-no-digest"),
            pytest.param(
                {"manifest": {"layers": ["not-a-dict", {"size": 1}]}},
                id="layers-not-dicts-or-no-digest",
            ),
        ],
    )
    def test_get_referenced_blobs_ignores_malformed_manifest_documents(
        self, storage, write_manifest_file, document
    ):
        """Test that malformed manifest documents contribute no referenced blobs."""
        # Arrange
        write_manifest_file("3.22.4", document)

        # Act
        referenced = storage.get_referenced_blobs()

        # Assert
        assert referenced == set()
