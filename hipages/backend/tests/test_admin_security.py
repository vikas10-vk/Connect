import pytest

from services.admin_security import AdminBootstrapError, validate_admin_bootstrap


def test_admin_bootstrap_allows_owner_email_with_secret(monkeypatch):
    monkeypatch.setenv("OWNER_ADMIN_EMAILS", "owner@example.com, other@example.com")
    monkeypatch.setenv("ADMIN_BOOTSTRAP_TOKEN", "secret-token")

    email = validate_admin_bootstrap(" Owner@Example.com ", "secret-token")

    assert email == "owner@example.com"


def test_admin_bootstrap_rejects_non_owner_email(monkeypatch):
    monkeypatch.setenv("OWNER_ADMIN_EMAILS", "owner@example.com")
    monkeypatch.setenv("ADMIN_BOOTSTRAP_TOKEN", "secret-token")

    with pytest.raises(AdminBootstrapError, match="not allowed"):
        validate_admin_bootstrap("teammate@example.com", "secret-token")


def test_admin_bootstrap_rejects_missing_secret(monkeypatch):
    monkeypatch.setenv("OWNER_ADMIN_EMAILS", "owner@example.com")
    monkeypatch.delenv("ADMIN_BOOTSTRAP_TOKEN", raising=False)

    with pytest.raises(AdminBootstrapError, match="not configured"):
        validate_admin_bootstrap("owner@example.com", "secret-token")


def test_admin_bootstrap_rejects_wrong_secret(monkeypatch):
    monkeypatch.setenv("OWNER_ADMIN_EMAILS", "owner@example.com")
    monkeypatch.setenv("ADMIN_BOOTSTRAP_TOKEN", "secret-token")

    with pytest.raises(AdminBootstrapError, match="Invalid"):
        validate_admin_bootstrap("owner@example.com", "wrong-token")
