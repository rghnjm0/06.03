import pytest
from services.passwords import hash_password, password_matches, validate_password


def test_password_hash_is_not_plaintext():
    password = 'Correct-Horse-42!'
    hashed = hash_password(password)
    assert hashed != password
    assert password_matches(hashed, password)
    assert not password_matches(hashed, 'wrong-password')


def test_password_policy_limits():
    with pytest.raises(ValueError):
        validate_password('short')
    with pytest.raises(ValueError):
        validate_password('x' * 257)


def test_legacy_plaintext_is_rejected():
    assert not password_matches('plain-text-secret', 'plain-text-secret')


def test_password_validation_rejects_non_string_values():
    for value in (None, 123, b"bytes"):
        with pytest.raises(ValueError):
            validate_password(value)


def test_password_hashes_are_salted():
    password = "Same-password-123!"
    assert hash_password(password) != hash_password(password)


def test_empty_or_missing_hash_never_authenticates():
    assert not password_matches(None, "anything")
    assert not password_matches("", "anything")
