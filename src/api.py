import logging
from typing import List

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .routes.auth import auth_router
from .routes.oci import oci_router
from .settings import storage

logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)

app = FastAPI(docs_url="/api/v1/docs", title="registry", version="0.0.0")

logger.info('📦 Using "%s" storage backend', storage)


# Pydantic models for pagination
class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints"""

    limit: int = Field(
        default=10, ge=1, le=100, description="Number of items per request"
    )
    offset: int = Field(default=0, ge=0, description="Number of items to skip")


class RepositoryListResponse(BaseModel):
    """Response model for repository list endpoint"""

    repositories: List[str]
    total: int
    limit: int
    offset: int


app.include_router(auth_router)
app.include_router(oci_router)


@app.get("/api/v1/repositories", response_model=RepositoryListResponse)
async def list_repositories(
    limit: int = Query(
        default=10, ge=1, le=100, description="Number of items per request"
    ),
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
):
    """List repositories with limit/offset pagination"""
    # Get all repositories
    all_repos = sorted(storage.list_repositories())
    total = len(all_repos)

    # Get paginated slice
    repos_page = all_repos[offset : offset + limit]

    return RepositoryListResponse(
        repositories=repos_page,
        total=total,
        limit=limit,
        offset=offset,
    )


@app.delete("/api/v1/repositories/{repo:path}")
async def delete_repository(repo: str):
    """Delete a repository and its manifests, cleaning up unreferenced blobs"""
    # Check if repository exists
    if repo not in storage.list_repositories():
        raise HTTPException(status_code=404, detail="Repository not found")

    # Get all manifests for this repository before deletion
    manifests_to_delete = storage.get_all_manifests_for_repo(repo)

    # Delete the repository (removes from list and all its manifests)
    storage.delete_repository(repo)

    # Get the set of blobs still referenced by other manifests
    referenced_blobs = storage.get_referenced_blobs()

    # Collect all blobs that were in the deleted manifests
    blobs_to_check: set[str] = set()
    for manifest_data in manifests_to_delete:
        if "manifest" in manifest_data and isinstance(manifest_data["manifest"], dict):
            manifest = manifest_data["manifest"]
            # Extract blob references from manifest
            if "config" in manifest and isinstance(manifest["config"], dict):
                if "digest" in manifest["config"]:
                    blobs_to_check.add(manifest["config"]["digest"])
            if "layers" in manifest and isinstance(manifest["layers"], list):
                for layer in manifest["layers"]:
                    if isinstance(layer, dict) and "digest" in layer:
                        blobs_to_check.add(layer["digest"])

    # Delete blobs that are no longer referenced
    for blob_digest in blobs_to_check:
        if blob_digest not in referenced_blobs and storage.blob_exists(blob_digest):
            storage.delete_blob(blob_digest)

    return JSONResponse(
        content={"message": f"Repository '{repo}' deleted successfully"},
        status_code=202,
    )


def server():
    """Run the registry server on port 5000"""
    print("📦 registry")

    host = "0.0.0.0"
    port = 5000

    logger.info("http://%s:%s", host, port)

    uvicorn.run(app, host=host, port=port, log_level="debug")
