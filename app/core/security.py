import hashlib
import hmac
import os

_ALGO = "pbkdf2_sha256"
_ITERATIONS = 390000
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    salt = os.urandom(_SALT_BYTES).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), _ITERATIONS).hex()
    return f"{_ALGO}${_ITERATIONS}${salt}${digest}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        algo, iterations_text, salt_hex, digest_hex = hashed_password.split("$", 3)
        if algo != _ALGO:
            return False
        iterations = int(iterations_text)
    except ValueError:
        return False

    computed = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), bytes.fromhex(salt_hex), iterations).hex()
    return hmac.compare_digest(computed, digest_hex)
