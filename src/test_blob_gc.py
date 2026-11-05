"""Tests for garbage collection of blobs when a manifest is deleted.

Deleting a tag removes its manifest and drops the digest copy once no other tag
points at it. Config and layer blobs are removed only when nothing else
references them.
"""

import hashlib
import json

MANIFEST_TYPE = "application/vnd.docker.distribution.manifest.v2+json"


def push(client, repo: str, tag: str, config: str, layers: list[str]) -> str:
    """Push an image manifest through the OCI API and return its digest."""
    body = json.dumps(
        {
            "schemaVersion": 2,
            "mediaType": MANIFEST_TYPE,
            "config": {"digest": config},
            "layers": [{"digest": layer} for layer in layers],
        }
    ).encode()
    response = client.put(
        f"/v2/{repo}/manifests/{tag}",
        content=body,
        headers={"Content-Type": MANIFEST_TYPE},
    )
    assert response.status_code == 201
    return f"sha256:{hashlib.sha256(body).hexdigest()}"


class TestDeleteTagGarbageCollection:
    """Deleting a tag through the OCI API."""

    def test_unshared_blobs_are_removed(self, client):
        """Test that the config and layers of a deleted-only image are freed."""
        # Arrange
        from src.api import storage

        push(client, "alpine", "3.22.4", "sha256:cfg", ["sha256:l1"])
        storage.put_blob("sha256:cfg", b"config")
        storage.put_blob("sha256:l1", b"layer")

        # Act
        response = client.delete("/v2/alpine/manifests/3.22.4")

        # Assert
        assert response.status_code == 202
        assert not storage.blob_exists("sha256:cfg")
        assert not storage.blob_exists("sha256:l1")

    def test_digest_copy_is_removed_with_last_tag(self, client):
        """Test that the digest-addressed copy goes when no tag points at it."""
        # Arrange
        from src.api import storage

        digest = push(client, "alpine", "3.22.4", "sha256:cfg", ["sha256:l1"])

        # Act
        client.delete("/v2/alpine/manifests/3.22.4")

        # Assert
        assert not storage.manifest_exists("alpine", "3.22.4")
        assert not storage.manifest_exists("alpine", digest)

    def test_shared_layer_is_kept_while_another_tag_uses_it(self, client):
        """Test that a layer used by a remaining tag survives the delete."""
        # Arrange
        from src.api import storage

        push(client, "alpine", "3.22.4", "sha256:cfg1", ["sha256:shared"])
        push(client, "alpine", "latest", "sha256:cfg2", ["sha256:shared"])
        storage.put_blob("sha256:cfg1", b"config1")
        storage.put_blob("sha256:shared", b"layer")

        # Act
        client.delete("/v2/alpine/manifests/3.22.4")

        # Assert
        assert not storage.blob_exists("sha256:cfg1")
        assert storage.blob_exists("sha256:shared")

    def test_digest_copy_is_kept_while_another_tag_points_at_it(self, client):
        """Test that deleting one of two tags on the same image keeps the digest copy."""
        # Arrange
        from src.api import storage

        digest = push(client, "alpine", "3.22.4", "sha256:cfg", ["sha256:l1"])
        push(client, "alpine", "latest", "sha256:cfg", ["sha256:l1"])
        storage.put_blob("sha256:cfg", b"config")
        storage.put_blob("sha256:l1", b"layer")

        # Act
        response = client.delete("/v2/alpine/manifests/3.22.4")

        # Assert
        assert response.status_code == 202
        assert storage.manifest_exists("alpine", digest)
        assert storage.blob_exists("sha256:cfg")
        assert storage.blob_exists("sha256:l1")

    def test_deleting_last_tag_after_sibling_removed_frees_blobs(self, client):
        """Test that removing both tags eventually frees the shared image blobs."""
        # Arrange
        from src.api import storage

        push(client, "alpine", "3.22.4", "sha256:cfg", ["sha256:l1"])
        push(client, "alpine", "latest", "sha256:cfg", ["sha256:l1"])
        storage.put_blob("sha256:cfg", b"config")
        storage.put_blob("sha256:l1", b"layer")

        # Act
        client.delete("/v2/alpine/manifests/3.22.4")
        client.delete("/v2/alpine/manifests/latest")

        # Assert
        assert not storage.blob_exists("sha256:cfg")
        assert not storage.blob_exists("sha256:l1")

    def test_digest_delete_does_not_trigger_blob_removal(self, client):
        """Test that deleting by digest (not a tag) leaves blobs alone."""
        # Arrange
        from src.api import storage

        digest = push(client, "alpine", "3.22.4", "sha256:cfg", ["sha256:l1"])
        storage.put_blob("sha256:cfg", b"config")

        # Act
        response = client.delete(f"/v2/alpine/manifests/{digest}")

        # Assert
        assert response.status_code == 202
        assert storage.blob_exists("sha256:cfg")


class TestDeleteWithIndex:
    """Blobs of child manifests listed by an index are not freed by tag deletes."""

    def test_child_blobs_survive_deleting_the_index(self, client):
        """Test that deleting an index leaves its children's blobs referenced."""
        # Arrange
        from src.api import storage

        child_digest = push(client, "alpine", "amd64", "sha256:ccfg", ["sha256:clyr"])
        index_body = json.dumps({"manifests": [{"digest": child_digest}]}).encode()
        client.put(
            "/v2/alpine/manifests/latest",
            content=index_body,
            headers={"Content-Type": "application/vnd.oci.image.index.v1+json"},
        )
        storage.put_blob("sha256:ccfg", b"config")
        storage.put_blob("sha256:clyr", b"layer")

        # Act
        client.delete("/v2/alpine/manifests/latest")

        # Assert
        assert storage.blob_exists("sha256:ccfg")
        assert storage.blob_exists("sha256:clyr")
