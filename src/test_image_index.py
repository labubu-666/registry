"""Tests that an image index keeps its child manifests from being deleted."""

from src.storage.schema import ManifestData

CHILD_DIGEST = "sha256:child"
INDEX_TYPE = "application/vnd.oci.image.index.v1+json"


def make_child() -> ManifestData:
    """Build an image manifest stored under its own digest."""
    return ManifestData(
        manifest={
            "config": {"digest": "sha256:child-cfg"},
            "layers": [{"digest": "sha256:child-layer"}],
        },
        body=b"child",
        digest=CHILD_DIGEST,
    )


def make_index(children: list[str]) -> ManifestData:
    """Build an image index that lists the given child digests."""
    return ManifestData(
        manifest={"manifests": [{"digest": d} for d in children]},
        content_type=INDEX_TYPE,
        body=b"index",
        digest="sha256:index",
    )


class TestChildDeleteGuard:
    """Deleting a child manifest that an index still references."""

    def test_delete_child_referenced_by_index_returns_409(self, client):
        """Test that a child digest used by an index cannot be deleted."""
        # Arrange
        from src.api import storage

        storage.add_repository("alpine")
        storage.put_manifest("alpine", CHILD_DIGEST, make_child())
        storage.put_manifest("alpine", "latest", make_index([CHILD_DIGEST]))

        # Act
        response = client.delete(f"/v2/alpine/manifests/{CHILD_DIGEST}")

        # Assert
        assert response.status_code == 409
        assert storage.manifest_exists("alpine", CHILD_DIGEST)

    def test_delete_child_not_referenced_by_index_succeeds(self, client):
        """Test that a digest no index lists can still be deleted."""
        # Arrange
        from src.api import storage

        storage.add_repository("alpine")
        storage.put_manifest("alpine", CHILD_DIGEST, make_child())
        storage.put_manifest("alpine", "latest", make_index(["sha256:other"]))

        # Act
        response = client.delete(f"/v2/alpine/manifests/{CHILD_DIGEST}")

        # Assert
        assert response.status_code == 202
        assert not storage.manifest_exists("alpine", CHILD_DIGEST)

    def test_delete_child_by_tag_referenced_by_index_returns_409(self, client):
        """Test that a child cannot be deleted through a tag that points at it."""
        # Arrange
        from src.api import storage

        storage.add_repository("alpine")
        storage.put_manifest("alpine", CHILD_DIGEST, make_child())
        storage.put_manifest("alpine", "v1", make_child())
        storage.put_manifest("alpine", "latest", make_index([CHILD_DIGEST]))

        # Act
        response = client.delete("/v2/alpine/manifests/v1")

        # Assert
        assert response.status_code == 409
        assert storage.manifest_exists("alpine", "v1")
        assert storage.manifest_exists("alpine", CHILD_DIGEST)

    def test_delete_index_itself_succeeds(self, client):
        """Test that deleting the index is allowed even though it lists children."""
        # Arrange
        from src.api import storage

        storage.add_repository("alpine")
        storage.put_manifest("alpine", CHILD_DIGEST, make_child())
        storage.put_manifest("alpine", "latest", make_index([CHILD_DIGEST]))

        # Act
        response = client.delete("/v2/alpine/manifests/latest")

        # Assert
        assert response.status_code == 202
        assert not storage.manifest_exists("alpine", "latest")

    def test_child_is_deletable_once_index_is_gone(self, client):
        """Test that removing the index releases the child for deletion."""
        # Arrange
        from src.api import storage

        storage.add_repository("alpine")
        storage.put_manifest("alpine", CHILD_DIGEST, make_child())
        storage.put_manifest("alpine", "latest", make_index([CHILD_DIGEST]))
        client.delete("/v2/alpine/manifests/latest")

        # Act
        response = client.delete(f"/v2/alpine/manifests/{CHILD_DIGEST}")

        # Assert
        assert response.status_code == 202
