"""Garbage collection of blobs that no manifest references."""

from collections.abc import Iterable

from .base import BaseStorage


def delete_unreferenced_blobs(storage: BaseStorage, candidates: Iterable[str]) -> None:
    """Delete candidate blobs that no stored manifest references.

    Args:
        storage: The storage backend to clean.
        candidates: Blob digests that might have just become unreferenced,
            for example the layers of a manifest that was just deleted.
    """
    referenced = storage.get_referenced_blobs()
    for digest in set(candidates):
        if digest not in referenced and storage.blob_exists(digest):
            storage.delete_blob(digest)
