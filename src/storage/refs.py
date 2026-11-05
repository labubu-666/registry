"""Helpers for reading references between manifests."""

from typing import Any


def child_manifest_digests(manifest: dict[str, Any]) -> list[str]:
    """Return the child manifest digests listed in an image index's ``manifests[]``.

    Malformed entries are ignored. Image manifests (no ``manifests`` list)
    return an empty list.
    """
    children = manifest.get("manifests")
    if not isinstance(children, list):
        return []

    digests: list[str] = []
    for child in children:
        if isinstance(child, dict) and isinstance(child.get("digest"), str):
            digests.append(child["digest"])
    return digests


def manifest_blob_digests(manifest: dict[str, Any]) -> set[str]:
    """Return the config and layer blob digests of an image manifest.

    Malformed entries are ignored. Image indexes return an empty set, because
    their children are separate manifests and own their own blobs.
    """
    digests: set[str] = set()

    config = manifest.get("config")
    if isinstance(config, dict) and isinstance(config.get("digest"), str):
        digests.add(config["digest"])

    layers = manifest.get("layers")
    if isinstance(layers, list):
        for layer in layers:
            if isinstance(layer, dict) and isinstance(layer.get("digest"), str):
                digests.add(layer["digest"])

    return digests
