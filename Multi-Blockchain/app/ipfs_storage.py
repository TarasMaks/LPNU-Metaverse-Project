"""IPFS hybrid storage layer.

Implements the off-chain storage model where large data objects (3D models,
tensors, sensor archives) are stored on IPFS while the blockchain records
only the Content Identifier (CID).  This ensures data immutability with
minimal on-chain storage costs.

When the IPFS API is not available, the module falls back to a local
in-memory store for development and testing purposes.
"""

from __future__ import annotations

import base64
import hashlib
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class IPFSStorage:
    """Client for pinning and resolving data via IPFS.

    Falls back to a local dict-based store when the IPFS daemon is
    unreachable, making it safe for unit tests and offline development.
    """

    def __init__(
        self,
        api_url: str = "",
        gateway_url: str = "https://ipfs.io/ipfs/",
    ) -> None:
        self._api_url = api_url
        self._gateway_url = gateway_url.rstrip("/")
        self._connected = False

        # Local fallback store for development / tests
        self._local_store: Dict[str, bytes] = {}

        if api_url:
            self._try_connect()
        else:
            logger.info("No IPFS_API_URL – using local fallback store")

    def _try_connect(self) -> None:
        """Attempt to connect to the IPFS HTTP API."""
        try:
            import httpx

            resp = httpx.post(
                f"{self._api_url}/api/v0/id",
                timeout=5.0,
            )
            if resp.status_code == 200:
                self._connected = True
                logger.info("Connected to IPFS node: %s", self._api_url)
            else:
                logger.warning("IPFS node returned status %d", resp.status_code)
        except Exception as exc:
            logger.warning("Cannot connect to IPFS: %s – using local store", exc)

    @property
    def is_connected(self) -> bool:
        return self._connected

    @staticmethod
    def compute_cid(data: bytes) -> str:
        """Compute a deterministic CID-like identifier from raw bytes.

        Uses SHA-256 and a ``Qm``-style prefix for compatibility.  A real
        implementation would use the full CIDv1/multihash specification.
        """
        digest = hashlib.sha256(data).hexdigest()
        return f"Qm{digest}"

    def pin(self, data_b64: str, filename: str = "") -> dict:
        """Pin base-64 encoded data, returning the CID and size.

        Returns:
            dict with keys: cid, size_bytes, gateway_url
        """
        raw = base64.b64decode(data_b64)
        cid = self.compute_cid(raw)

        if self._connected:
            pinned = self._pin_remote(raw, filename)
            if pinned:
                return pinned

        # Fallback to local store
        self._local_store[cid] = raw
        logger.debug("Pinned locally: %s (%d bytes)", cid, len(raw))
        return {
            "cid": cid,
            "size_bytes": len(raw),
            "gateway_url": f"{self._gateway_url}/{cid}",
        }

    def resolve(self, cid: str) -> Optional[dict]:
        """Resolve a CID and return the data as base-64.

        Returns:
            dict with keys: cid, data, size_bytes   –or–  None
        """
        if self._connected:
            result = self._resolve_remote(cid)
            if result:
                return result

        raw = self._local_store.get(cid)
        if raw is None:
            return None
        return {
            "cid": cid,
            "data": base64.b64encode(raw).decode(),
            "size_bytes": len(raw),
        }

    # ── Remote IPFS operations ───────────────────────────────

    def _pin_remote(self, raw: bytes, filename: str) -> Optional[dict]:
        try:
            import httpx

            files = {"file": (filename or "data", raw)}
            resp = httpx.post(
                f"{self._api_url}/api/v0/add",
                files=files,
                timeout=30.0,
            )
            if resp.status_code == 200:
                result = resp.json()
                cid = result.get("Hash", "")
                size = int(result.get("Size", len(raw)))
                return {
                    "cid": cid,
                    "size_bytes": size,
                    "gateway_url": f"{self._gateway_url}/{cid}",
                }
        except Exception as exc:
            logger.warning("Remote IPFS pin failed: %s", exc)
        return None

    def _resolve_remote(self, cid: str) -> Optional[dict]:
        try:
            import httpx

            resp = httpx.post(
                f"{self._api_url}/api/v0/cat",
                params={"arg": cid},
                timeout=30.0,
            )
            if resp.status_code == 200:
                raw = resp.content
                return {
                    "cid": cid,
                    "data": base64.b64encode(raw).decode(),
                    "size_bytes": len(raw),
                }
        except Exception as exc:
            logger.warning("Remote IPFS resolve failed: %s", exc)
        return None
