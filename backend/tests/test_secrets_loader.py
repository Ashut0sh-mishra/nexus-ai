"""Phase 6AM — encrypted-secrets loader tests.

Round-trips the Fernet encrypt/decrypt path and asserts the loader's
safety contract: it never overrides explicit env vars (host dashboard
wins), never crashes on a bad key, and is a no-op without the master key.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from cryptography.fernet import Fernet

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from secrets_loader import load_encrypted_env  # noqa: E402

_PLAINTEXT = (
    "GROQ_API_KEY=secret-groq-123\n"
    "# a comment line\n"
    "\n"
    'QUOTED_VALUE="wrapped-in-quotes"\n'
    "NEXUS_API_KEY=lockdown-key\n"
)


def _write_enc(tmp_path: Path, key: str) -> Path:
    enc = tmp_path / ".env.enc"
    enc.write_bytes(Fernet(key.encode()).encrypt(_PLAINTEXT.encode()))
    return enc


def _clear(*names: str) -> None:
    for n in names:
        os.environ.pop(n, None)


def test_no_op_without_master_key(tmp_path):
    enc = _write_enc(tmp_path, Fernet.generate_key().decode())
    # No key supplied and NEXUS_SECRETS_KEY absent → no-op.
    _clear("NEXUS_SECRETS_KEY")
    assert load_encrypted_env(enc_path=enc, key=None) is False


def test_decrypts_and_populates_unset_vars(tmp_path):
    key = Fernet.generate_key().decode()
    enc = _write_enc(tmp_path, key)
    _clear("GROQ_API_KEY", "NEXUS_API_KEY", "QUOTED_VALUE")
    try:
        applied = load_encrypted_env(enc_path=enc, key=key)
        assert applied is True
        assert os.environ["GROQ_API_KEY"] == "secret-groq-123"
        assert os.environ["NEXUS_API_KEY"] == "lockdown-key"
        # surrounding quotes are stripped
        assert os.environ["QUOTED_VALUE"] == "wrapped-in-quotes"
    finally:
        _clear("GROQ_API_KEY", "NEXUS_API_KEY", "QUOTED_VALUE")


def test_does_not_override_explicit_env(tmp_path):
    key = Fernet.generate_key().decode()
    enc = _write_enc(tmp_path, key)
    os.environ["GROQ_API_KEY"] = "host-dashboard-value"
    _clear("NEXUS_API_KEY", "QUOTED_VALUE")
    try:
        load_encrypted_env(enc_path=enc, key=key)
        # Host value preserved; only the unset var was filled.
        assert os.environ["GROQ_API_KEY"] == "host-dashboard-value"
        assert os.environ["NEXUS_API_KEY"] == "lockdown-key"
    finally:
        _clear("GROQ_API_KEY", "NEXUS_API_KEY", "QUOTED_VALUE")


def test_override_true_replaces_existing(tmp_path):
    key = Fernet.generate_key().decode()
    enc = _write_enc(tmp_path, key)
    os.environ["GROQ_API_KEY"] = "host-dashboard-value"
    try:
        load_encrypted_env(enc_path=enc, key=key, override=True)
        assert os.environ["GROQ_API_KEY"] == "secret-groq-123"
    finally:
        _clear("GROQ_API_KEY", "NEXUS_API_KEY", "QUOTED_VALUE")


def test_wrong_key_fails_gracefully(tmp_path):
    enc = _write_enc(tmp_path, Fernet.generate_key().decode())
    wrong = Fernet.generate_key().decode()
    _clear("GROQ_API_KEY", "NEXUS_API_KEY")
    # Different valid Fernet key → decrypt raises internally → returns False.
    assert load_encrypted_env(enc_path=enc, key=wrong) is False
    assert "GROQ_API_KEY" not in os.environ


def test_missing_file_returns_false(tmp_path):
    key = Fernet.generate_key().decode()
    assert load_encrypted_env(enc_path=tmp_path / "nope.enc", key=key) is False
