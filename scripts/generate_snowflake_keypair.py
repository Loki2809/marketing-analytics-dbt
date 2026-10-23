"""Create an RSA key pair for Snowflake key-pair login.

The keys are saved in your home folder (~/.snowflake), outside this repo,
so the private key can never be committed to Git.

Run from the project root with the venv active:
    python scripts/generate_snowflake_keypair.py
"""

from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

KEY_DIR = Path.home() / ".snowflake"
PRIVATE_KEY_PATH = KEY_DIR / "rsa_key.p8"
PUBLIC_KEY_PATH = KEY_DIR / "rsa_key.pub"


def main() -> None:
    # Never overwrite an existing key: Snowflake would stop accepting the old one.
    if PRIVATE_KEY_PATH.exists() or PUBLIC_KEY_PATH.exists():
        print(f"Keys already exist in {KEY_DIR}. Nothing was changed.")
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

    PRIVATE_KEY_PATH.write_bytes(private_pem)
    PUBLIC_KEY_PATH.write_bytes(public_pem)

    # Snowflake wants the public key as one line, without the BEGIN/END lines.
    public_key_one_line = "".join(
        line for line in public_pem.decode().splitlines() if not line.startswith("-----")
    )

    print(f"Private key (keep secret): {PRIVATE_KEY_PATH}")
    print(f"Public key:                {PUBLIC_KEY_PATH}")
    print()
    print("Public key for Snowflake (safe to share):")
    print(public_key_one_line)


if __name__ == "__main__":
    main()
