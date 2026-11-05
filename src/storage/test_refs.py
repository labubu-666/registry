"""Tests for extracting child manifest digests from image indexes."""

import pytest

from src.storage.refs import child_manifest_digests


@pytest.mark.parametrize(
    "manifest,expected",
    [
        pytest.param(
            {"manifests": [{"digest": "sha256:a"}, {"digest": "sha256:b"}]},
            ["sha256:a", "sha256:b"],
            id="index-with-children",
        ),
        pytest.param({"config": {"digest": "sha256:cfg"}}, [], id="image-manifest"),
        pytest.param({"manifests": []}, [], id="empty-index"),
        pytest.param({"manifests": "not-a-list"}, [], id="manifests-not-list"),
        pytest.param({"manifests": ["not-a-dict"]}, [], id="entry-not-dict"),
        pytest.param({"manifests": [{"size": 1}]}, [], id="entry-without-digest"),
    ],
)
def test_child_manifest_digests(manifest, expected):
    """Test that only well-formed manifests[] digests are returned, in order."""
    # Act
    digests = child_manifest_digests(manifest)

    # Assert
    assert digests == expected
