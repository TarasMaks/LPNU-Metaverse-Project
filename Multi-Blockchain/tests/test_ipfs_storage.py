"""Tests for IPFS hybrid storage (using local fallback)."""

import base64

from app.ipfs_storage import IPFSStorage


def test_local_pin_and_resolve():
    ipfs = IPFSStorage()
    data = base64.b64encode(b"hello IPFS").decode()

    result = ipfs.pin(data)
    assert "cid" in result
    assert result["size_bytes"] == len(b"hello IPFS")
    assert result["cid"].startswith("Qm")

    resolved = ipfs.resolve(result["cid"])
    assert resolved is not None
    assert resolved["cid"] == result["cid"]
    assert base64.b64decode(resolved["data"]) == b"hello IPFS"


def test_resolve_unknown_cid_returns_none():
    ipfs = IPFSStorage()
    assert ipfs.resolve("QmNONEXISTENT") is None


def test_compute_cid_deterministic():
    cid1 = IPFSStorage.compute_cid(b"test data")
    cid2 = IPFSStorage.compute_cid(b"test data")
    assert cid1 == cid2
    assert cid1.startswith("Qm")


def test_compute_cid_different_data():
    cid1 = IPFSStorage.compute_cid(b"data A")
    cid2 = IPFSStorage.compute_cid(b"data B")
    assert cid1 != cid2


def test_not_connected_without_api_url():
    ipfs = IPFSStorage()
    assert not ipfs.is_connected


def test_pin_with_filename():
    ipfs = IPFSStorage()
    data = base64.b64encode(b"file content").decode()
    result = ipfs.pin(data, filename="test.bin")
    assert result["cid"].startswith("Qm")
    assert result["size_bytes"] == len(b"file content")
