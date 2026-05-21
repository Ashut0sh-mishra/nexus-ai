"""Phase 6AM — encrypt / decrypt the NEXUS .env into a committable .env.enc.

All your API keys can live in the repo encrypted, decrypted only at runtime
with one master key (``NEXUS_SECRETS_KEY``). See ``backend/secrets_loader.py``.

Usage (run from the backend/ directory):

    # 1) Generate a master key (keep it secret; this is your ONE host secret):
    python -m scripts.secrets_crypt keygen

    # 2) Encrypt your filled-in .env -> .env.enc (commit .env.enc, NOT .env):
    python -m scripts.secrets_crypt encrypt --key <MASTER_KEY>
    #    (defaults: src=.env  dst=.env.enc)

    # 3) Sanity-check the round trip (prints decrypted plaintext to stdout):
    python -m scripts.secrets_crypt decrypt --key <MASTER_KEY>

On the host (Render/Fly) set a single secret:  NEXUS_SECRETS_KEY=<MASTER_KEY>
and commit .env.enc. The app decrypts it on boot.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cryptography.fernet import Fernet

_BACKEND = Path(__file__).resolve().parent.parent
_DEFAULT_SRC = _BACKEND / ".env"
_DEFAULT_ENC = _BACKEND / ".env.enc"


def _keygen() -> int:
    print(Fernet.generate_key().decode("utf-8"))
    return 0


def _encrypt(src: Path, dst: Path, key: str) -> int:
    if not src.is_file():
        print(f"error: source file not found: {src}", file=sys.stderr)
        return 2
    data = src.read_bytes()
    token = Fernet(key.encode("utf-8")).encrypt(data)
    dst.write_bytes(token)
    print(f"encrypted {src} -> {dst} ({len(token)} bytes). Safe to commit {dst.name}.")
    return 0


def _decrypt(enc: Path, key: str) -> int:
    if not enc.is_file():
        print(f"error: encrypted file not found: {enc}", file=sys.stderr)
        return 2
    try:
        plaintext = Fernet(key.encode("utf-8")).decrypt(enc.read_bytes()).decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        print(f"error: decryption failed (wrong key?): {exc}", file=sys.stderr)
        return 1
    sys.stdout.write(plaintext)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="secrets_crypt")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("keygen", help="generate a new Fernet master key")

    enc = sub.add_parser("encrypt", help="encrypt a plaintext env file")
    enc.add_argument("--src", type=Path, default=_DEFAULT_SRC)
    enc.add_argument("--dst", type=Path, default=_DEFAULT_ENC)
    enc.add_argument("--key", required=True)

    dec = sub.add_parser("decrypt", help="decrypt an encrypted env file to stdout")
    dec.add_argument("--src", type=Path, default=_DEFAULT_ENC)
    dec.add_argument("--key", required=True)

    args = parser.parse_args(argv)
    if args.cmd == "keygen":
        return _keygen()
    if args.cmd == "encrypt":
        return _encrypt(args.src, args.dst, args.key)
    if args.cmd == "decrypt":
        return _decrypt(args.src, args.key)
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
