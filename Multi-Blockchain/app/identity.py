"""PUF-based canonical identity module.

Implements the binding between a physical subject and their digital twin
using Physically Unclonable Functions (PUF) with biometric authentication.
The PUF response is hashed into an NFT token (ERC-721/1155) on the
settlement layer, creating a canonical identity that is:

- Tied to the subject's unique physical characteristics
- Immutable and verifiable on-chain
- Resistant to identity theft and impersonation
- Represented as a non-fungible token for interoperability
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from typing import Optional

from .settlement import SettlementClient

logger = logging.getLogger(__name__)


class CanonicalIdentityManager:
    """Manages canonical identities backed by PUF commitments and NFTs.

    Each identity consists of:
    - A deterministic DID derived from the PUF commitment
    - A PUF commitment (hash of the biometric PUF response + salt)
    - An NFT token on the settlement layer (when blockchain is available)
    """

    def __init__(
        self,
        settlement_client: Optional[SettlementClient] = None,
        hash_algorithm: str = "sha256",
    ) -> None:
        self._settlement = settlement_client
        self._hash_alg = hash_algorithm

    def compute_puf_commitment(self, puf_response: str, salt: str = "") -> str:
        """Derive a deterministic commitment from a PUF response.

        The commitment is ``HMAC-SHA256(salt, puf_response)`` so that the
        same PUF response always yields the same commitment given the same
        salt, enabling verification without revealing the raw response.
        """
        if not salt:
            salt = uuid.uuid4().hex
        commitment = hmac.new(
            salt.encode(),
            puf_response.encode(),
            hashlib.sha256,
        ).hexdigest()
        return commitment

    def derive_did(self, puf_commitment: str) -> str:
        """Derive a DID from the PUF commitment using the ``did:puf`` method.

        Format: ``did:puf:<sha256(commitment)[:32]>``
        """
        digest = hashlib.sha256(puf_commitment.encode()).hexdigest()[:32]
        return f"did:puf:{digest}"

    def generate_token_id(self, did: str) -> str:
        """Generate a deterministic token ID from a DID."""
        return hashlib.sha256(did.encode()).hexdigest()[:16]

    def register(
        self,
        subject_id: str,
        puf_response: str,
        wallet_address: str,
        metadata_uri: str = "",
    ) -> dict:
        """Register a new canonical identity.

        Returns a dict with: token_id, did, puf_commitment, nft_tx_hash.
        """
        salt = hashlib.sha256(subject_id.encode()).hexdigest()[:16]
        commitment = self.compute_puf_commitment(puf_response, salt)
        did = self.derive_did(commitment)
        token_id = self.generate_token_id(did)

        nft_tx_hash: Optional[str] = None
        if self._settlement and self._settlement.is_enabled:
            receipt = self._settlement.mint_identity(
                wallet=wallet_address,
                puf_commitment=commitment,
                metadata_uri=metadata_uri,
            )
            if receipt:
                nft_tx_hash = receipt.tx_hash

        return {
            "token_id": token_id,
            "did": did,
            "puf_commitment": commitment,
            "nft_tx_hash": nft_tx_hash,
        }

    def verify(self, subject_id: str, puf_response: str, stored_commitment: str) -> dict:
        """Verify a PUF response against a stored commitment.

        Re-derives the commitment from the response and compares it to
        the stored value.  Returns verification result with confidence.
        """
        salt = hashlib.sha256(subject_id.encode()).hexdigest()[:16]
        computed = self.compute_puf_commitment(puf_response, salt)
        verified = hmac.compare_digest(computed, stored_commitment)

        did = self.derive_did(stored_commitment)
        token_id = self.generate_token_id(did)

        return {
            "verified": verified,
            "did": did,
            "token_id": token_id,
            "confidence": 1.0 if verified else 0.0,
        }
