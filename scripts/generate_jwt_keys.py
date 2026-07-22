#!/usr/bin/env python3
"""Generate an RSA key pair for RS256 JWT signing.

Usage:
    python scripts/generate_jwt_keys.py [--kid KEY_ID]

Prints:
- The private key PEM. Store it in your secret manager and inject it as the
  ``JWT_PRIVATE_KEY_PEM`` env var (never commit it).
- A JSON snippet mapping ``kid`` to the public key PEM. Merge it into the
  ``JWT_PUBLIC_KEYS_PEM`` env var (a JSON dict of kid -> public key PEM) so
  the API can verify tokens. During rotation keep the old entry alongside
  the new one until all tokens signed with the old key have expired.

Example rotation flow:
    1. python scripts/generate_jwt_keys.py --kid key-2026-08
    2. Set JWT_PRIVATE_KEY_PEM to the new private key, JWT_KEY_ID=key-2026-08.
    3. Add the new public key to JWT_PUBLIC_KEYS_PEM, keeping the old kid.
    4. After JWT_EXPIRATION_MINUTES has elapsed, remove the old public key.
"""

import argparse
import json
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--kid",
        default="key-1",
        help="Key ID embedded in JWT headers (default: key-1)",
    )
    parser.add_argument(
        "--bits",
        type=int,
        default=2048,
        help="RSA key size in bits (default: 2048)",
    )
    args = parser.parse_args()

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=args.bits)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )

    print("# Private key PEM -> store in secret manager, set as JWT_PRIVATE_KEY_PEM")
    print(private_pem)
    print("# Public key JSON -> merge into JWT_PUBLIC_KEYS_PEM")
    print(json.dumps({args.kid: public_pem}))
    print(f"# Set JWT_KEY_ID={args.kid}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
