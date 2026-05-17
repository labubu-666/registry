"""Tests for the OCI Distribution v2 API endpoints (/v2/...)."""

import hashlib
import json

import pytest


class TestV2Catalog:
    """Tests for GET /v2/_catalog"""

    def test_catalog_with_mixed_nested_and_flat_paths(self, client):
        """Test that catalog correctly lists both nested and flat repository paths."""
        # Arrange
        from src.api import storage

        repos = [
            "alpine",
            "ubuntu",
            "my/repo",
            "org/team/project",
            "user/myrepo",
        ]
        for repo in repos:
            storage.add_repository(repo)

        # Act
        response = client.get("/v2/_catalog")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert set(data["repositories"]) == set(repos)


class TestManifestOperations:
    """Tests for manifest push/pull/delete via OCI endpoints."""

    @pytest.mark.parametrize(
        "repo_name",
        [
            "my/repo",
            "username/myrepo",
            "org/team/project",
            "deep/nested/path/to/repo",
        ],
    )
    def test_put_and_get_manifest_with_nested_path(self, client, repo_name):
        """Test pushing and pulling manifests with nested repository paths."""
        # Arrange
        manifest = {
            "schemaVersion": 2,
            "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
            "config": {"digest": "sha256:config1", "size": 100},
        }
        manifest_json = json.dumps(manifest)

        # Act - PUT manifest
        response_put = client.put(
            f"/v2/{repo_name}/manifests/latest",
            content=manifest_json,
            headers={
                "Content-Type": "application/vnd.docker.distribution.manifest.v2+json"
            },
        )

        # Assert PUT
        assert response_put.status_code == 201
        assert "Docker-Content-Digest" in response_put.headers

        # Act - GET manifest
        response_get = client.get(f"/v2/{repo_name}/manifests/latest")

        # Assert GET
        assert response_get.status_code == 200
        assert response_get.json() == manifest

    @pytest.mark.parametrize(
        "repo_name",
        [
            "my/repo",
            "org/team/project",
        ],
    )
    def test_head_manifest_with_nested_path(self, client, repo_name):
        """Test HEAD request to check manifest exists with nested paths."""
        # Arrange
        manifest = {
            "schemaVersion": 2,
            "config": {"digest": "sha256:config1", "size": 100},
        }
        manifest_json = json.dumps(manifest)

        client.put(
            f"/v2/{repo_name}/manifests/latest",
            content=manifest_json,
            headers={
                "Content-Type": "application/vnd.docker.distribution.manifest.v2+json"
            },
        )

        # Act
        response = client.head(f"/v2/{repo_name}/manifests/latest")

        # Assert
        assert response.status_code == 200
        assert "Docker-Content-Digest" in response.headers

    @pytest.mark.parametrize(
        "repo_name,tag",
        [
            ("user/repo", "v1.0"),
            ("org/team/project", "latest"),
        ],
    )
    def test_delete_manifest_with_nested_path(self, client, repo_name, tag):
        """Test deleting manifests in nested repository paths."""
        # Arrange
        from src.api import storage

        manifest = {
            "schemaVersion": 2,
            "config": {"digest": "sha256:config1", "size": 100},
        }
        manifest_json = json.dumps(manifest)

        client.put(
            f"/v2/{repo_name}/manifests/{tag}",
            content=manifest_json,
            headers={
                "Content-Type": "application/vnd.docker.distribution.manifest.v2+json"
            },
        )
        assert storage.manifest_exists(repo_name, tag)

        # Act
        response = client.delete(f"/v2/{repo_name}/manifests/{tag}")

        # Assert
        assert response.status_code == 202
        assert not storage.manifest_exists(repo_name, tag)

    @pytest.mark.parametrize(
        "repo_name,tag",
        [
            ("user/app", "v1.0.0"),
            ("company/team/service", "latest"),
            ("my/multi/level/deep/repo", "staging"),
        ],
    )
    def test_deeply_nested_paths(self, client, repo_name, tag):
        """Test support for deeply nested repository paths."""
        # Arrange
        manifest = {
            "schemaVersion": 2,
            "config": {"digest": "sha256:config1", "size": 100},
        }
        manifest_json = json.dumps(manifest)

        # Act
        response = client.put(
            f"/v2/{repo_name}/manifests/{tag}",
            content=manifest_json,
            headers={
                "Content-Type": "application/vnd.docker.distribution.manifest.v2+json"
            },
        )

        # Assert
        assert response.status_code == 201

        response_get = client.get(f"/v2/{repo_name}/manifests/{tag}")
        assert response_get.status_code == 200
        assert response_get.json() == manifest


class TestTagListing:
    """Tests for GET /v2/{name}/tags/list"""

    @pytest.mark.parametrize(
        "repo_name",
        [
            "my/repo",
            "user/project",
        ],
    )
    def test_list_tags_with_nested_path(self, client, repo_name):
        """Test listing tags for nested repository paths."""
        # Arrange
        manifest = {
            "schemaVersion": 2,
            "config": {"digest": "sha256:config1", "size": 100},
        }
        manifest_json = json.dumps(manifest)

        tags = ["v1.0", "v2.0", "latest"]
        for tag in tags:
            client.put(
                f"/v2/{repo_name}/manifests/{tag}",
                content=manifest_json,
                headers={
                    "Content-Type": "application/vnd.docker.distribution.manifest.v2+json"
                },
            )

        # Act
        response = client.get(f"/v2/{repo_name}/tags/list")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == repo_name
        assert set(data["tags"]) == set(tags)


class TestBlobOperations:
    """Tests for blob upload/download via OCI endpoints."""

    @pytest.mark.parametrize(
        "repo_name",
        [
            "my/repo",
            "org/project",
        ],
    )
    def test_blob_operations_with_nested_path(self, client, repo_name):
        """Test blob upload and download with nested repository paths."""
        # Arrange
        blob_data = b"test blob content"
        blob_digest = f"sha256:{hashlib.sha256(blob_data).hexdigest()}"

        # Act - Initiate upload
        response_init = client.post(f"/v2/{repo_name}/blobs/uploads/")
        assert response_init.status_code == 202
        upload_location = response_init.headers["Location"]
        upload_id = upload_location.split("/")[-1]

        # Act - Complete upload
        response_complete = client.put(
            f"/v2/{repo_name}/blobs/uploads/{upload_id}?digest={blob_digest}",
            content=blob_data,
        )
        assert response_complete.status_code == 201

        # Act - GET blob
        response_get = client.get(f"/v2/{repo_name}/blobs/{blob_digest}")
        assert response_get.status_code == 200
        assert response_get.content == blob_data

        # Act - HEAD blob
        response_head = client.head(f"/v2/{repo_name}/blobs/{blob_digest}")
        assert response_head.status_code == 200
        assert response_head.headers["Docker-Content-Digest"] == blob_digest
