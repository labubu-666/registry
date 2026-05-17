import hashlib
import json
import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from src.settings import settings, storage
from src.auth.middleware import CurrentUser
from src.storage.schema import ManifestData

logger = logging.getLogger(__name__)

oci_router = APIRouter(prefix="", tags=["Open Container Initiative"])


def _www_authenticate() -> str:
    """Build the WWW-Authenticate challenge header value."""
    return f'Bearer realm="{settings.auth_realm}",service="{settings.auth_service}"'


@oci_router.get("/v2/")
async def v2_base(authorization: Optional[str] = Header(default=None)):
    """Docker Registry v2 API base endpoint.

    Returns 401 when no Bearer token is present so Docker knows where to
    obtain one.  Any valid token (including an anonymous one issued by
    /auth/token) is accepted and results in a 200 response.
    """
    if not (authorization and authorization.lower().startswith("bearer ")):
        return Response(
            content='{"errors":[{"code":"UNAUTHORIZED","message":"authentication required"}]}',
            status_code=401,
            media_type="application/json",
            headers={
                "Docker-Distribution-API-Version": "registry/2.0",
                "WWW-Authenticate": _www_authenticate(),
            },
        )

    return Response(
        content="{}",
        status_code=200,
        headers={
            "Docker-Distribution-API-Version": "registry/2.0",
            "Content-Type": "application/json",
        },
    )


@oci_router.get("/v2/_catalog")
async def catalog(user: CurrentUser):
    """List all repositories in the registry"""
    logger.debug("catalog requested by %r", user)
    repos = storage.list_repositories()
    return JSONResponse(
        content={"repositories": repos},
        headers={"Docker-Distribution-API-Version": "registry/2.0"},
    )


@oci_router.get("/v2/{name:path}/tags/list")
async def list_tags(name: str, user: CurrentUser):
    """List all tags for a given repository"""
    logger.debug("listing tags for %r requested by %r", name, user)
    tags = storage.list_tags(name)

    return JSONResponse(
        content={"name": name, "tags": tags},
        headers={"Docker-Distribution-API-Version": "registry/2.0"},
    )


@oci_router.head("/v2/{name:path}/manifests/{reference}")
async def head_manifest(name: str, reference: str, user: CurrentUser):
    """Check if a manifest exists"""
    logger.debug("head manifest %r/%r requested by %r", name, reference, user)
    manifest_data = storage.get_manifest(name, reference)
    if manifest_data is None:
        raise HTTPException(status_code=404, detail="Manifest not found")
    # Use stored body to ensure consistent digest calculation
    content = manifest_data.get("body", json.dumps(manifest_data["manifest"]).encode())
    if isinstance(content, str):
        content = content.encode()
    digest = manifest_data.get(
        "digest", f"sha256:{hashlib.sha256(content).hexdigest()}"
    )

    return Response(
        status_code=200,
        headers={
            "Docker-Distribution-API-Version": "registry/2.0",
            "Content-Type": manifest_data.get(
                "content_type", "application/vnd.docker.distribution.manifest.v2+json"
            ),
            "Docker-Content-Digest": digest,
            "Content-Length": str(len(content)),
        },
    )


@oci_router.get("/v2/{name:path}/manifests/{reference}")
async def get_manifest(name: str, reference: str, user: CurrentUser):
    """Get a manifest by tag or digest"""
    logger.debug("get manifest %r/%r requested by %r", name, reference, user)
    manifest_data = storage.get_manifest(name, reference)
    if manifest_data is None:
        raise HTTPException(status_code=404, detail="Manifest not found")
    # Use stored body to ensure consistent digest calculation
    content = manifest_data.get("body", json.dumps(manifest_data["manifest"]).encode())
    if isinstance(content, str):
        content = content.encode()

    digest = manifest_data.get(
        "digest", f"sha256:{hashlib.sha256(content).hexdigest()}"
    )

    return Response(
        content=content,
        media_type=manifest_data.get(
            "content_type", "application/vnd.docker.distribution.manifest.v2+json"
        ),
        headers={
            "Docker-Distribution-API-Version": "registry/2.0",
            "Docker-Content-Digest": digest,
        },
    )


@oci_router.put("/v2/{name:path}/manifests/{reference}")
async def put_manifest(
    name: str,
    reference: str,
    request: Request,
    user: CurrentUser,
    content_type: Optional[str] = Header(None),
):
    """Upload a manifest"""
    logger.debug("put manifest %r/%r by %r", name, reference, user)
    body = await request.body()
    manifest = json.loads(body)

    digest = f"sha256:{hashlib.sha256(body).hexdigest()}"

    # Store manifest data with both tag and digest for later retrieval
    manifest_data = ManifestData(
        manifest=manifest,
        content_type=content_type
        or "application/vnd.docker.distribution.manifest.v2+json",
        body=body,
        digest=digest,
    )

    # Store by tag (e.g., "alpine:3.22.4")
    storage.put_manifest(name, reference, manifest_data)

    # Also store by digest (e.g., "alpine:sha256:abc123...") so pulls can retrieve by digest
    storage.put_manifest(name, digest, manifest_data)

    storage.add_repository(name)

    return Response(
        status_code=201,
        headers={
            "Docker-Distribution-API-Version": "registry/2.0",
            "Docker-Content-Digest": digest,
            "Location": f"/v2/{name}/manifests/{digest}",
        },
    )


@oci_router.head("/v2/{name:path}/blobs/{digest}")
async def head_blob(name: str, digest: str, user: CurrentUser):
    """Check if a blob exists"""
    logger.debug("head blob %r/%r requested by %r", name, digest, user)
    blob_data = storage.get_blob(digest)
    if blob_data is None:
        raise HTTPException(status_code=404, detail="Blob not found")

    return Response(
        status_code=200,
        headers={
            "Docker-Distribution-API-Version": "registry/2.0",
            "Content-Length": str(len(blob_data)),
            "Docker-Content-Digest": digest,
        },
    )


@oci_router.get("/v2/{name:path}/blobs/{digest}")
async def get_blob(name: str, digest: str, user: CurrentUser):
    """Download a blob"""
    logger.debug("get blob %r/%r requested by %r", name, digest, user)
    blob_data = storage.get_blob(digest)
    if blob_data is None:
        raise HTTPException(status_code=404, detail="Blob not found")

    return Response(
        content=blob_data,
        media_type="application/octet-stream",
        headers={
            "Docker-Distribution-API-Version": "registry/2.0",
            "Docker-Content-Digest": digest,
        },
    )


@oci_router.post("/v2/{name:path}/blobs/uploads/")
async def initiate_blob_upload(name: str, user: CurrentUser):
    """Initiate a blob upload"""
    import uuid

    logger.debug("initiate blob upload for %r by %r", name, user)
    upload_id = str(uuid.uuid4())

    return Response(
        status_code=202,
        headers={
            "Docker-Distribution-API-Version": "registry/2.0",
            "Location": f"/v2/{name}/blobs/uploads/{upload_id}",
            "Range": "0-0",
        },
    )


@oci_router.put("/v2/{name:path}/blobs/uploads/{uuid}")
async def complete_blob_upload(
    name: str, uuid: str, digest: str, request: Request, user: CurrentUser
):
    """Complete a blob upload"""
    logger.debug("complete blob upload for %r/%r by %r", name, uuid, user)
    body = await request.body()

    # Verify digest
    calculated_digest = f"sha256:{hashlib.sha256(body).hexdigest()}"
    if digest != calculated_digest:
        raise HTTPException(status_code=400, detail="Digest mismatch")

    storage.put_blob(digest, body)

    return Response(
        status_code=201,
        headers={
            "Docker-Distribution-API-Version": "registry/2.0",
            "Docker-Content-Digest": digest,
            "Location": f"/v2/{name}/blobs/{digest}",
        },
    )


@oci_router.delete("/v2/{name:path}/manifests/{reference}")
async def delete_manifest(name: str, reference: str, user: CurrentUser):
    """Delete a manifest"""
    logger.debug("delete manifest %r/%r by %r", name, reference, user)
    if not storage.manifest_exists(name, reference):
        raise HTTPException(status_code=404, detail="Manifest not found")

    storage.delete_manifest(name, reference)

    return Response(
        status_code=202, headers={"Docker-Distribution-API-Version": "registry/2.0"}
    )
