"""Create an RSA key pair for Snowflake key-pair login.

The keys are saved in your home folder (~/.snowflake), outside this repo,
so the private key can never be committed to Git.

Run from the project root with the venv active:
    python scripts/generate_snowflake_keypair.py          -> rsa_key.p8 / rsa_key.pub   (your own login)
    python scripts/generate_snowflake_keypair.py ci       -> ci_rsa_key.p8 / ci_rsa_key.pub (the CI service user)

The optional name lets each Snowflake user have its own key pair.
"""

import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

KEY_DIR = Path.home() / ".snowflake"


def main() -> None:
    # Optional first argument: a name prefix, e.g. "ci" -> ci_rsa_key.p8
    prefix = f"{sys.argv[1]}_" if len(sys.argv) > 1 else ""
    private_key_path = KEY_DIR / f"{prefix}rsa_key.p8"
    public_key_path = KEY_DIR / f"{prefix}rsa_key.pub"

    # Never overwrite an existing key: Snowflake would stop accepting the old one.
    if private_key_path.exists() or public_key_path.exists():
        print(f"Keys already exist: {private_key_path}. Nothing was changed.")
        return

    KEY_DIR.mkdir(exist_ok=True)

    # 2048-bit RSA is the minimum size Snowflake accepts.
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    private_key_path.write_bytes(private_pem)
    public_key_path.write_bytes(public_pem)

    # Snowflake wants the public key as one line, without the BEGIN/END lines.
    public_key_one_line = "".join(
        line for line in public_pem.decode().splitlines() if not line.startswith("-----")
    )

    print(f"Private key (keep secret): {private_key_path}")
    print(f"Public key:                {public_key_path}")
    print()
    print("Public key for Snowflake (safe to share):")
    print(public_key_one_line)


if __name__ == "__main__":
    main()
