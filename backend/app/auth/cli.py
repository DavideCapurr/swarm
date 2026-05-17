"""Operator-store admin CLI.

Tiny helpers for the operations team:

    python -m backend.app.auth.cli hash-password [password]
        Print a PBKDF2 envelope safe to paste into `password_hash`.

    python -m backend.app.auth.cli new-mfa <operator_id>
        Print a fresh TOTP secret + provisioning URI for enrolment.

    python -m backend.app.auth.cli verify <operators.yaml>
        Parse the YAML and report counts/duplicates without writing.

Stdin is read when the password is not on the command line so the secret
never lands in shell history.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

from backend.app.auth.mfa import generate_totp_secret, provisioning_uri
from backend.app.auth.passwords import hash_password
from backend.app.auth.store import load_operator_store


def _hash_password(args: argparse.Namespace) -> int:
    password = args.password
    if not password:
        password = getpass.getpass("password: ")
        confirm = getpass.getpass("confirm: ")
        if password != confirm:
            print("error: passwords do not match", file=sys.stderr)
            return 2
    if not password:
        print("error: empty password", file=sys.stderr)
        return 2
    print(hash_password(password))
    return 0


def _new_mfa(args: argparse.Namespace) -> int:
    secret = generate_totp_secret()
    uri = provisioning_uri(args.operator_id, secret)
    print(f"operator_id : {args.operator_id}")
    print(f"mfa_secret  : {secret}")
    print(f"otpauth uri : {uri}")
    return 0


def _verify(args: argparse.Namespace) -> int:
    path = Path(args.path)
    store = load_operator_store(path)
    print(f"loaded {len(store)} operator(s) from {path}")
    for op in store.all():
        flag = " (disabled)" if op.disabled else ""
        mfa = " [mfa]" if op.mfa_secret else ""
        print(f"  - {op.operator_id} role={op.role.value}{mfa}{flag}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m backend.app.auth.cli",
        description="SwarmOS auth admin helpers (Phase 6.C).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_hash = sub.add_parser("hash-password", help="print PBKDF2 envelope")
    p_hash.add_argument("password", nargs="?")
    p_hash.set_defaults(func=_hash_password)

    p_mfa = sub.add_parser("new-mfa", help="generate TOTP secret + URI")
    p_mfa.add_argument("operator_id")
    p_mfa.set_defaults(func=_new_mfa)

    p_verify = sub.add_parser("verify", help="parse a YAML operator config")
    p_verify.add_argument("path")
    p_verify.set_defaults(func=_verify)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
