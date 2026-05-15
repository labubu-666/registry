"""Tests for the custom REST API endpoints (/api/v1/...)."""

from src.storage.schema import ManifestData


class TestRepositoriesListPagination:
    """Tests for GET /api/v1/repositories"""

    def test_list_repositories_empty(self, client):
        """Test listing repositories when none exist"""
        # Act
        response = client.get("/api/v1/repositories")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["repositories"] == []
        assert data["total"] == 0
        assert data["limit"] == 10
        assert data["offset"] == 0

    def test_list_repositories_single(self, client):
        """Test listing a single repository"""
        # Arrange
        from src.api import storage

        storage.add_repository("alpine")

        # Act
        response = client.get("/api/v1/repositories")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["repositories"] == ["alpine"]
        assert data["total"] == 1

    def test_list_repositories_multiple(self, client):
        """Test listing multiple repositories"""
        # Arrange
        from src.api import storage

        storage.add_repository("alpine")
        storage.add_repository("ubuntu")
        storage.add_repository("python")

        # Act
        response = client.get("/api/v1/repositories")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert set(data["repositories"]) == {"alpine", "python", "ubuntu"}
        assert data["total"] == 3

    def test_list_repositories_pagination_first_offset(self, client):
        """Test pagination - first offset"""
        # Arrange
        from src.api import storage

        for i in range(15):
            storage.add_repository(f"repo{i:02d}")

        # Act
        response = client.get("/api/v1/repositories?limit=5&offset=0")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["repositories"]) == 5
        assert data["offset"] == 0
        assert data["limit"] == 5
        assert data["total"] == 15

    def test_list_repositories_pagination_second_offset(self, client):
        """Test pagination - second offset"""
        # Arrange
        from src.api import storage

        for i in range(15):
            storage.add_repository(f"repo{i:02d}")

        # Act
        response = client.get("/api/v1/repositories?limit=5&offset=5")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["repositories"]) == 5
        assert data["offset"] == 5
        assert data["limit"] == 5

    def test_list_repositories_pagination_last_offset(self, client):
        """Test pagination - last offset with fewer items"""
        # Arrange
        from src.api import storage

        for i in range(15):
            storage.add_repository(f"repo{i:02d}")

        # Act
        response = client.get("/api/v1/repositories?limit=5&offset=10")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["repositories"]) == 5
        assert data["offset"] == 10

    def test_list_repositories_default_pagination(self, client):
        """Test default pagination values"""
        # Arrange
        from src.api import storage

        for i in range(5):
            storage.add_repository(f"repo{i}")

        # Act
        response = client.get("/api/v1/repositories")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 0

    def test_list_repositories_invalid_offset(self, client):
        """Test that negative offset is rejected with validation error"""
        # Arrange
        from src.api import storage

        storage.add_repository("alpine")

        # Act
        response = client.get("/api/v1/repositories?offset=-1")

        # Assert
        assert response.status_code == 422

    def test_list_repositories_invalid_limit(self, client):
        """Test that limit over max is rejected with validation error"""
        # Arrange
        from src.api import storage

        storage.add_repository("alpine")

        # Act
        response = client.get("/api/v1/repositories?limit=101")

        # Assert
        assert response.status_code == 422

    def test_list_repositories_sorted(self, client):
        """Test that repositories are sorted alphabetically"""
        # Arrange
        from src.api import storage

        storage.add_repository("zebra")
        storage.add_repository("alpha")
        storage.add_repository("beta")

        # Act
        response = client.get("/api/v1/repositories")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["repositories"] == ["alpha", "beta", "zebra"]

    def test_list_repositories_includes_nested_paths(self, client):
        """Test that listing repositories includes nested paths"""
        # Arrange
        from src.api import storage

        repos = [
            "alpine",
            "user/repo1",
            "user/repo2",
            "org/team/project",
        ]
        for repo in repos:
            storage.add_repository(repo)

        # Act
        response = client.get("/api/v1/repositories")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert set(data["repositories"]) == set(repos)
        assert data["total"] == 4


class TestRepositoryDeletion:
    """Tests for DELETE /api/v1/repositories/{repo}"""

    def test_delete_repository_success(self, client):
        """Test deleting an existing repository"""
        # Arrange
        from src.api import storage

        storage.add_repository("alpine")

        # Act
        response = client.delete("/api/v1/repositories/alpine")

        # Assert
        assert response.status_code == 202
        data = response.json()
        assert "deleted successfully" in data["message"].lower()
        assert "alpine" not in storage.list_repositories()

    def test_delete_repository_not_found(self, client):
        """Test deleting a non-existent repository"""
        # Act
        response = client.delete("/api/v1/repositories/nonexistent")

        # Assert
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_delete_repository_removes_manifests(self, client):
        """Test that deleting a repository removes its manifests"""
        # Arrange
        from src.api import storage

        manifest_data = ManifestData(
            manifest={"config": {"digest": "sha256:blob1"}},
            content_type="application/vnd.docker.distribution.manifest.v2+json",
            body=b"manifest",
            digest="sha256:manifest1",
        )
        storage.add_repository("alpine")
        storage.put_manifest("alpine", "3.22.4", manifest_data)
        assert storage.manifest_exists("alpine", "3.22.4")

        # Act
        response = client.delete("/api/v1/repositories/alpine")

        # Assert
        assert response.status_code == 202
        assert not storage.manifest_exists("alpine", "3.22.4")

    def test_delete_repository_preserves_other_repos(self, client):
        """Test that deleting a repository doesn't affect others"""
        # Arrange
        from src.api import storage

        storage.add_repository("alpine")
        storage.add_repository("ubuntu")

        # Act
        response = client.delete("/api/v1/repositories/alpine")

        # Assert
        assert response.status_code == 202
        assert "ubuntu" in storage.list_repositories()
        assert "alpine" not in storage.list_repositories()

    def test_delete_repository_with_multiple_manifests(self, client):
        """Test deleting a repository with multiple manifests"""
        # Arrange
        from src.api import storage

        manifest_data = ManifestData(
            manifest={"config": {"digest": "sha256:blob1"}},
            content_type="application/vnd.docker.distribution.manifest.v2+json",
            body=b"manifest",
            digest="sha256:manifest1",
        )
        storage.add_repository("alpine")
        storage.put_manifest("alpine", "3.22.4", manifest_data)
        storage.put_manifest("alpine", "latest", manifest_data)

        # Act
        response = client.delete("/api/v1/repositories/alpine")

        # Assert
        assert response.status_code == 202
        assert not storage.manifest_exists("alpine", "3.22.4")
        assert not storage.manifest_exists("alpine", "latest")

    def test_delete_repository_with_unreferenced_blobs(self, client):
        """Test that unreferenced blobs are deleted during repository deletion"""
        # Arrange
        from src.api import storage

        manifest_data = ManifestData(
            manifest={
                "config": {"digest": "sha256:config1"},
                "layers": [{"digest": "sha256:layer1"}],
            },
            content_type="application/vnd.docker.distribution.manifest.v2+json",
            body=b"manifest",
            digest="sha256:manifest1",
        )
        storage.add_repository("alpine")
        storage.put_manifest("alpine", "3.22.4", manifest_data)
        storage.put_blob("sha256:config1", b"config")
        storage.put_blob("sha256:layer1", b"layer")

        # Act
        response = client.delete("/api/v1/repositories/alpine")

        # Assert
        assert response.status_code == 202
        # Blobs should be deleted since they are no longer referenced
        assert not storage.blob_exists("sha256:config1")
        assert not storage.blob_exists("sha256:layer1")

    def test_delete_repository_preserves_shared_blobs(self, client):
        """Test that blobs shared with other repos are not deleted"""
        # Arrange
        from src.api import storage

        shared_blob_digest = "sha256:shared_blob"
        manifest_alpine = ManifestData(
            manifest={"config": {"digest": shared_blob_digest}},
            content_type="application/vnd.docker.distribution.manifest.v2+json",
            body=b"alpine_manifest",
            digest="sha256:manifest_alpine",
        )
        manifest_ubuntu = ManifestData(
            manifest={"config": {"digest": shared_blob_digest}},
            content_type="application/vnd.docker.distribution.manifest.v2+json",
            body=b"ubuntu_manifest",
            digest="sha256:manifest_ubuntu",
        )

        storage.add_repository("alpine")
        storage.add_repository("ubuntu")
        storage.put_manifest("alpine", "3.22.4", manifest_alpine)
        storage.put_manifest("ubuntu", "22.04", manifest_ubuntu)
        storage.put_blob(shared_blob_digest, b"shared blob data")

        # Act - delete alpine
        response = client.delete("/api/v1/repositories/alpine")

        # Assert
        assert response.status_code == 202
        # Shared blob should still be referenced by ubuntu
        assert shared_blob_digest in storage.get_referenced_blobs()
        # And the blob file should still exist
        assert storage.blob_exists(shared_blob_digest)

    def test_delete_repository_with_nested_path(self, client):
        """Test deleting a nested repository via API endpoint"""
        # Arrange
        from src.api import storage

        repo_name = "my/repo"
        storage.add_repository(repo_name)
        assert repo_name in storage.list_repositories()

        # Act
        response = client.delete(f"/api/v1/repositories/{repo_name}")

        # Assert
        assert response.status_code == 202
        assert "deleted successfully" in response.json()["message"].lower()
        assert repo_name not in storage.list_repositories()

    def test_nested_path_with_repository_deletion_and_blob_cleanup(self, client):
        """Test that deleting nested repo also cleans up unreferenced blobs"""
        # Arrange
        import json
        from typing import Any

        from src.api import storage

        repo_name = "org/team/project"
        shared_blob_digest = "sha256:shared_blob"

        manifest: dict[str, Any] = {
            "schemaVersion": 2,
            "config": {"digest": shared_blob_digest, "size": 100},
        }

        storage.add_repository(repo_name)
        storage.put_manifest(
            repo_name,
            "latest",
            ManifestData(
                manifest=manifest,
                content_type="application/vnd.docker.distribution.manifest.v2+json",
                body=json.dumps(manifest).encode(),
                digest="sha256:manifest1",
            ),
        )
        storage.put_blob(shared_blob_digest, b"shared blob data")
        assert storage.blob_exists(shared_blob_digest)

        # Act
        response = client.delete(f"/api/v1/repositories/{repo_name}")

        # Assert
        assert response.status_code == 202
        assert repo_name not in storage.list_repositories()
        # Blob should be deleted since it's unreferenced
        assert not storage.blob_exists(shared_blob_digest)


class TestEchoEndpointRemoved:
    """Tests to verify echo endpoint is removed"""

    def test_echo_endpoint_not_found(self, client):
        """Test that /echo endpoint no longer exists"""
        # Act
        response = client.get("/echo")

        # Assert
        assert response.status_code == 404
