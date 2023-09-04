from simod_http.auth import _verify_password, _get_password_hash


def test_verify_password():
    hashed_password = _get_password_hash("test")
    assert _verify_password("test", hashed_password)
