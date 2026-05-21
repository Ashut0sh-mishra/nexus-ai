"""Phase 6AM — encrypted-secrets loader.

Lets every API key live in the repo **encrypted** (``.env.enc``) instead of
as plaintext. At boot, if ``NEXUS_SECRETS_KEY`` is present in the
environment, this module decrypts ``.env.enc`` with that single master key
and populates ``os.environ`` — *without* overriding any value already set
explicitly in the environment (so Render/Fly dashboard vars still win).

Flow:
    1. You encrypt your filled-in ``.env`` once:  python -m scripts.secrets_crypt encrypt
    2. Commit the resulting ``.env.enc`` (values are AES-encrypted — safe).
    3. Set ONE secret in the host (Render/Fly): ``NEXUS_SECRETS_KEY``.
    4. On boot this loader decrypts ``.env.enc`` into the process env.

Security properties:
    * Fernet (AES-128-CBC + HMAC-SHA256) authenticated encryption.
    * The committed ``.env.enc`` reveals nothing without the master key.
    * The master key is the ONLY plaintext secret you manage at the host.
    * Decryption never overrides explicit env vars, so you can still
      override any single value from the dashboard.

This is import-safe and total: any failure logs and returns False so the
app falls back to normal env / .env loading rather than crashing.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger("nexus.secrets")

_DEFAULT_ENC = Path(__file__).resolve().parent / ".env.enc"


def load_encrypted_env(
    enc_path: str | os.PathLike[str] | None = None,
    key: str | None = None,
    *,
    override: bool = False,
) -> bool:
    """Decrypt ``.env.enc`` into ``os.environ``. Returns True if applied.

    Parameters
    ----------
    enc_path:
        Path to the encrypted env file. Defaults to ``backend/.env.enc``.
    key:
        The Fernet master key. Defaults to ``os.environ["NEXUS_SECRETS_KEY"]``.
    override:
        When False (default) an already-set env var is left untouched, so a
        value pasted in the host dashboard always wins over the encrypted
        file. When True the decrypted value replaces it.
    """
    key = key or os.environ.get("NEXUS_SECRETS_KEY", "")
    if not key:
        return False

    path = Path(enc_path) if enc_path is not None else _DEFAULT_ENC
    if not path.is_file():
        logger.info("secrets.no_enc_file", extra={"path": str(path)})
        return False

    try:
        from cryptography.fernet import Fernet

        token = path.read_bytes()
        plaintext = Fernet(key.encode("utf-8")).decrypt(token).decode("utf-8")
    except Exception as exc:  # never crash boot on a bad key / corrupt file
        logger.error("secrets.decrypt_failed", extra={"err": str(exc)})
        return False

    applied = 0
    for raw_line in plaintext.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if not k:
            continue
        if override or k not in os.environ:
            os.environ[k] = v
            applied += 1

    logger.info("secrets.loaded", extra={"applied": applied})
    return applied > 0


__all__ = ["load_encrypted_env"]
