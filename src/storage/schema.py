from typing import Any

from pydantic import BaseModel, Field


class ManifestData(BaseModel):
    """Model for manifest data stored in registry"""

    manifest: dict[str, Any]
    content_type: str = Field(
        default="application/vnd.docker.distribution.manifest.v2+json",
        description="Content type of the manifest",
    )
    body: bytes
    digest: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ManifestData:
        """Create ManifestData from a dictionary, handling bytes conversion."""
        if isinstance(data.get("body"), str):
            # Handle base64-encoded body from file storage
            import base64

            data = dict(data)
            data["body"] = base64.b64decode(data["body"])
        return cls(**data)
