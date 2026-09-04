from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

from jobpilot_api.api.security import JOBPILOT_EXTENSION_ORIGIN


def test_api_extension_origin_matches_the_manifest_public_key() -> None:
    repository_root = Path(__file__).resolve().parents[4]
    identity = json.loads(
        (repository_root / "apps/extension/extension-public-key.json").read_text(encoding="utf-8")
    )
    assert set(identity) == {"publicKey"}
    public_key = base64.b64decode(identity["publicKey"], validate=True)
    digest = hashlib.sha256(public_key).digest()[:16]
    alphabet = "abcdefghijklmnop"
    extension_id = "".join(
        alphabet[nibble] for byte in digest for nibble in (byte >> 4, byte & 0x0F)
    )

    assert JOBPILOT_EXTENSION_ORIGIN == f"chrome-extension://{extension_id}"
