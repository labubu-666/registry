"""Tests for the blob garbage collector and manifest blob extraction."""

import pytest

from src.storage.gc import delete_unreferenced_blobs
from src.storage.memory import MemoryStorage
from src.storage.refs import manifest_blob_digests
from src.storage.schema import ManifestData


@pytest.fixture
def storage() -> MemoryStorage:
    """Provide an empty in-memory storage."""
    return MemoryStorage()


def put_image(storage, reference: str, config: str, layers: list[str]) -> None:
    """Store an image manifest referencing the given config and layers."""
    storage.put_manifest(
        "alpine",
        reference,
        ManifestData(
            manifest={
                "config": {"digest": config},
                "layers": [{"digest": layer} for layer in layers],
            },
            body=b"",
            digest=f"sha256:{reference}",
        ),
    )


class TestDeleteUnreferencedBlobs:
    """Behaviour of delete_unreferenced_blobs."""

    @pytest.mark.parametrize(
        "stored_blobs,candidates,expected_remaining",
        [
            pytest.param(["sha256:orphan"], ["sha256:orphan"], [], id="unreferenced"),
            pytest.param(
                ["sha256:l1"],
                ["sha256:l1"],
                ["sha256:l1"],
                id="referenced-by-manifest",
            ),
            pytest.param(
                ["sha256:dup"], ["sha256:dup", "sha256:dup"], [], id="duplicates"
            ),
            pytest.param(["sha256:keep"], [], ["sha256:keep"], id="no-candidates"),
            pytest.param([], ["sha256:missing"], [], id="not-stored"),
        ],
    )
    def test_delete_unreferenced_blobs(
        self, storage, stored_blobs, candidates, expected_remaining
    ):
        """Test that only candidates no manifest references are removed."""
        # Arrange
        put_image(storage, "latest", "sha256:cfg", ["sha256:l1"])
        for digest in stored_blobs:
            storage.put_blob(digest, b"x")

        # Act
        delete_unreferenced_blobs(storage, candidates)

        # Assert
        for digest in stored_blobs:
            assert storage.blob_exists(digest) == (digest in expected_remaining)


class TestManifestBlobDigests:
    """Behaviour of manifest_blob_digests."""

    @pytest.mark.parametrize(
        "manifest,expected",
        [
            pytest.param(
                {"config": {"digest": "sha256:c"}, "layers": [{"digest": "sha256:l"}]},
                {"sha256:c", "sha256:l"},
                id="image",
            ),
            pytest.param(
                {"manifests": [{"digest": "sha256:child"}]},
                set(),
                id="index-owns-no-blobs",
            ),
            pytest.param({"config": "not-a-dict"}, set(), id="config-not-dict"),
            pytest.param({"config": {"size": 1}}, set(), id="config-no-digest"),
            pytest.param({"layers": "not-a-list"}, set(), id="layers-not-list"),
            pytest.param(
                {"layers": ["not-a-dict", {"size": 1}, {"digest": 7}]},
                set(),
                id="layers-malformed-entries",
            ),
        ],
    )
    def test_manifest_blob_digests(self, manifest, expected):
        """Test that only well-formed config and layer digests are returned."""
        # Act
        digests = manifest_blob_digests(manifest)

        # Assert
        assert digests == expected
