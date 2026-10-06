from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHash

# Argon2id parameters:
#   time_cost=2, memory_cost=19456 (19 MB), parallelism=1
# This matches the OWASP Password Storage Cheat Sheet recommendation as of
# 2024 for Argon2id. Compared to the previous (time_cost=3, memory=65536,
# parallelism=2), this reduces peak memory per hash from ~128 MB to ~19 MB —
# critical on a 512 MB Render instance where concurrent logins would
# otherwise OOM. Security remains strong: the parameters still exceed
# interactive-login hardness targets by a wide margin.
_ph = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)


def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError, InvalidHash):
        return False


def needs_rehash(hashed: str) -> bool:
    return _ph.check_needs_rehash(hashed)