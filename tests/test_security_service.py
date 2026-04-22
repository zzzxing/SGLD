from app.core.security import hash_password, verify_password


def test_hash_and_verify_password() -> None:
    hashed = hash_password("123456")
    assert hashed.startswith("pbkdf2_sha256$")
    assert verify_password("123456", hashed)
    assert not verify_password("bad-password", hashed)
