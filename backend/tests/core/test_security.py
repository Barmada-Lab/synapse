from app.core.security import create_api_key, get_secret_hash, verify_secret


def test_secret_flow():
    secret = "secret"
    hashed_secret = get_secret_hash(secret)
    assert verify_secret(secret, hashed_secret)


def test_wrong_secret():
    secret = "secret"
    hashed_secret = get_secret_hash(secret)
    assert not verify_secret("wrong_secret", hashed_secret)


def test_api_key():
    api_key = create_api_key()
    hashed_api_key = get_secret_hash(api_key)
    assert verify_secret(api_key, hashed_api_key)


def test_wrong_api_key():
    api_key = create_api_key()
    hashed_api_key = get_secret_hash(api_key)
    assert not verify_secret(create_api_key(), hashed_api_key)
