"""Generate a VAPID key pair for Web Push.

Run once per environment:

    python -m app.notifications.vapid_gen

Copy the two lines into .env (local) and into Render's environment
variables (production). Never commit the private key.
"""
import base64
import os

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def main() -> None:
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()

    private_bytes = private_key.private_numbers().private_value.to_bytes(32, "big")
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )

    print("VAPID_PUBLIC_KEY=" + _b64url(public_bytes))
    print("VAPID_PRIVATE_KEY=" + _b64url(private_bytes))
    print("VAPID_SUBJECT=mailto:admin@campusos.app")


if __name__ == "__main__":
    main()