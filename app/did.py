from __future__ import annotations

import secrets


def generate_did(method: str = "example") -> str:
    suffix = secrets.token_hex(16)
    return f"did:{method}:{suffix}"
