import logging

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .routes.auth import auth_router
from .routes.oci import oci_router
from .settings import storage
from .storage.gc import delete_unreferenced_blobs
from .storage.refs import manifest_blob_digests

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

    repositories: list[str]
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

    # Collect the blobs the deleted manifests used, then free the ones nothing else uses
    candidates: set[str] = set()
    for manifest_data in manifests_to_delete:
        if isinstance(manifest_data.get("manifest"), dict):
            candidates |= manifest_blob_digests(manifest_data["manifest"])
    delete_unreferenced_blobs(storage, candidates)

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
