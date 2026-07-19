"""Tests for the registration/authentication models and schemas."""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from master_plan.api.auth_schemas import (
    LoginRequest,
    RegisterRequest,
    Token,
    TokenPayload,
    UserRecord,
    UserUpdate,
)
from master_plan.models import Credentials, Role, User, UserRegistration
from master_plan.models.auth import MIN_PASSWORD_LENGTH


def _registration(**overrides: object) -> UserRegistration:
    payload: dict[str, object] = {
        "email": "Ada@Example.COM",
        "username": "ada",
        "password": "correcthorse",
        "password_confirm": "correcthorse",
    }
    payload.update(overrides)
    return UserRegistration(**payload)


class TestUser:
    def test_defaults(self) -> None:
        user = User(email="ada@example.com", username="ada")
        assert user.role is Role.VIEWER
        assert user.is_active is True
        assert user.full_name is None

    def test_email_is_normalized_lowercase(self) -> None:
        user = User(email="Ada@Example.COM", username="ada")
        assert user.email == "ada@example.com"

    @pytest.mark.parametrize(
        "bad_email",
        ["not-an-email", "no@domain", "no@tld.", "a b@x.com", ""],
    )
    def test_invalid_email_is_rejected(self, bad_email: str) -> None:
        with pytest.raises(ValidationError):
            User(email=bad_email, username="ada")

    @pytest.mark.parametrize("bad", ["1ada", "_ada", "a", "ada__x", "ad!"])
    def test_invalid_username_is_rejected(self, bad: str) -> None:
        with pytest.raises(ValidationError):
            User(email="ada@example.com", username=bad)

    @pytest.mark.parametrize("ok", ["ada", "ada.lovelace", "a-b_c", "user1"])
    def test_valid_usernames_are_accepted(self, ok: str) -> None:
        assert User(email="ada@example.com", username=ok).username == ok

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            User(email="ada@example.com", username="ada", is_admin=True)


class TestUserRegistration:
    def test_passwords_must_match(self) -> None:
        with pytest.raises(ValidationError):
            _registration(password_confirm="different!!")

    def test_password_minimum_length_enforced(self) -> None:
        short = "a" * (MIN_PASSWORD_LENGTH - 1)
        with pytest.raises(ValidationError):
            _registration(password=short, password_confirm=short)

    def test_password_is_secret(self) -> None:
        reg = _registration()
        assert isinstance(reg.password, SecretStr)
        assert "correcthorse" not in repr(reg)

    def test_to_user_drops_password_and_normalizes(self) -> None:
        user = _registration().to_user()
        assert isinstance(user, User)
        assert user.email == "ada@example.com"
        assert user.role is Role.VIEWER
        assert not hasattr(user, "password")

    def test_to_user_accepts_role_override(self) -> None:
        assert _registration().to_user(role=Role.ADMIN).role is Role.ADMIN


class TestCredentials:
    def test_accepts_identifier_and_password(self) -> None:
        creds = Credentials(identifier="ada@example.com", password="whatever1")
        assert creds.identifier == "ada@example.com"
        assert creds.password.get_secret_value() == "whatever1"

    def test_empty_identifier_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Credentials(identifier="", password="whatever1")


class TestUserRecord:
    def test_from_user_carries_id_and_hash(self) -> None:
        user = User(email="ada@example.com", username="ada")
        record = UserRecord.from_user("u1", user, hashed_password="$argon2$abc")
        assert record.id == "u1"
        assert record.hashed_password == "$argon2$abc"

    def test_hash_excluded_from_serialization(self) -> None:
        record = UserRecord.from_user(
            "u1",
            User(email="ada@example.com", username="ada"),
            hashed_password="$argon2$abc",
        )
        assert "hashed_password" not in record.model_dump()

    def test_public_drops_id_and_hash(self) -> None:
        record = UserRecord.from_user(
            "u1",
            User(email="ada@example.com", username="ada"),
            hashed_password="$argon2$abc",
        )
        public = record.public()
        assert type(public) is User
        assert not hasattr(public, "id")


class TestUserUpdate:
    def test_apply_overlays_set_fields_only(self) -> None:
        user = User(email="ada@example.com", username="ada")
        updated = UserUpdate(role=Role.EDITOR).apply_to(user)
        assert updated.role is Role.EDITOR
        assert updated.username == "ada"
        assert updated.email == "ada@example.com"

    def test_deactivate(self) -> None:
        user = User(email="ada@example.com", username="ada")
        assert UserUpdate(is_active=False).apply_to(user).is_active is False


class TestTokens:
    def test_token_defaults_to_bearer(self) -> None:
        assert Token(access_token="abc").token_type == "bearer"

    def test_expires_in_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            Token(access_token="abc", expires_in=0)

    def test_token_payload_roundtrip(self) -> None:
        payload = TokenPayload(sub="u1", role=Role.ADMIN, exp=1_800_000_000)
        assert payload.sub == "u1"
        assert payload.role is Role.ADMIN


class TestAliases:
    def test_register_and_login_request_aliases(self) -> None:
        assert RegisterRequest is UserRegistration
        assert LoginRequest is Credentials
