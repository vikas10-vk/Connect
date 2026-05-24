import hmac
import os


class AdminBootstrapError(ValueError):
    """Raised when an admin bootstrap attempt is not explicitly authorized."""


def _parse_owner_admin_emails(raw: str | None = None) -> set[str]:
    value = os.getenv("OWNER_ADMIN_EMAILS", "") if raw is None else raw
    return {email.strip().lower() for email in value.split(",") if email.strip()}


def validate_admin_bootstrap(email: str, supplied_token: str | None) -> str:
    """
    Authorize direct admin creation/promotion.

    This protects the committed admin CLI from being usable by teammates who
    can read the repository but should not control production secrets.
    """
    normalized_email = email.strip().lower()
    owner_emails = _parse_owner_admin_emails()
    expected_token = os.getenv("ADMIN_BOOTSTRAP_TOKEN", "")

    if not owner_emails:
        raise AdminBootstrapError("OWNER_ADMIN_EMAILS is not configured.")

    if normalized_email not in owner_emails:
        raise AdminBootstrapError(
            "This email is not allowed to become an admin. "
            "Add only owner-controlled addresses to OWNER_ADMIN_EMAILS."
        )

    if not expected_token:
        raise AdminBootstrapError("ADMIN_BOOTSTRAP_TOKEN is not configured.")

    if not supplied_token or not hmac.compare_digest(supplied_token, expected_token):
        raise AdminBootstrapError("Invalid admin bootstrap token.")

    return normalized_email
