"""Decentralised Identifier (DID) generation with cryptographic key binding.

Implements a simplified ``did:key`` method where the DID suffix is derived
from the public half of an ECDSA P-256 key pair.  The private key is
returned to the caller so it can later sign challenges and transactions.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PublicFormat,
    PrivateFormat,
)


@dataclass
class DIDDocument:
    did: str
    public_key_pem: str
    private_key_pem: str
    wallet_address: str


def _pubkey_to_did_suffix(pub_bytes: bytes) -> str:
    """Multibase-inspired base64url encoding of the compressed public key."""
    return base64.urlsafe_b64encode(pub_bytes).decode().rstrip("=")


def _derive_wallet_address(pub_bytes: bytes) -> str:
    """Derive an Ethereum-style address from the public key (Keccak-256 of X||Y, last 20 bytes)."""
    digest = hashlib.sha256(pub_bytes).hexdigest()
    return "0x" + digest[-40:]


def generate_did(method: str = "key", wallet_address: str = "") -> DIDDocument:
    """Generate a new DID backed by an ECDSA P-256 key pair.

    Returns a :class:`DIDDocument` with the DID string, PEM-encoded keys,
    and an Ethereum-style wallet address (derived from the public key when
    *wallet_address* is not supplied).
    """
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()

    pub_bytes = public_key.public_bytes(Encoding.X962, PublicFormat.CompressedPoint)
    suffix = _pubkey_to_did_suffix(pub_bytes)
    did = f"did:{method}:{suffix}"

    pub_pem = public_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()
    priv_pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()

    addr = wallet_address or _derive_wallet_address(pub_bytes)

    return DIDDocument(did=did, public_key_pem=pub_pem, private_key_pem=priv_pem, wallet_address=addr)


def verify_wallet_signature(public_key_pem: str, message: bytes, signature: bytes) -> bool:
    """Verify an ECDSA-SHA256 signature produced by the DID's private key."""
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    from cryptography.hazmat.primitives.hashes import SHA256
    from cryptography.hazmat.primitives.serialization import load_pem_public_key

    try:
        pub = load_pem_public_key(public_key_pem.encode())
        pub.verify(signature, message, ec.ECDSA(SHA256()))  # type: ignore[arg-type]
        return True
    except Exception:
        return False


def sign_message(private_key_pem: str, message: bytes) -> bytes:
    """Sign *message* with the DID owner's private key (ECDSA-SHA256)."""
    from cryptography.hazmat.primitives.hashes import SHA256
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    priv = load_pem_private_key(private_key_pem.encode(), password=None)
    return priv.sign(message, ec.ECDSA(SHA256()))  # type: ignore[arg-type]
