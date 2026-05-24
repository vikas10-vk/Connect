# =============================================================================
# config.py Ã¢â‚¬â€ Application settings
# Tradie Platform
# =============================================================================

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, SecretStr, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=False)


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # =========================================================================
    # APPLICATION
    # =========================================================================

    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=False)
    INSTANCE_ID: str = Field(default="backend_dev")

    @computed_field  # type: ignore[misc]
    @property
    def IS_PRODUCTION(self) -> bool:
        return self.ENVIRONMENT == "production"

    @computed_field  # type: ignore[misc]
    @property
    def IS_DEVELOPMENT(self) -> bool:
        return self.ENVIRONMENT in ("development", "dev")

    # =========================================================================
    # DATABASE
    # =========================================================================

    DATABASE_URL: str = Field(description="Async PostgreSQL DSN.")
    DATABASE_POOL_SIZE: int = Field(default=10)
    DATABASE_MAX_OVERFLOW: int = Field(default=20)

    # =========================================================================
    # REDIS
    # =========================================================================

    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # =========================================================================
    # SECURITY Ã¢â‚¬â€ JWT
    #
    # FIX: Changed from plain str to SecretStr.
    # Before: SECRET_KEY appeared in plain text in any debug output, log dump,
    #         or str(settings) call Ã¢â‚¬â€ e.g. in Sentry breadcrumbs.
    # After:  SECRET_KEY.get_secret_value() to read. Appears as ***** everywhere else.
    # =========================================================================

    SECRET_KEY: SecretStr = Field(
        description=(
            "JWT signing key. Same env var name as auth_service.py Ã¢â‚¬â€ must match. "
            "Min 32 characters. Generate: openssl rand -base64 48"
        )
    )
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=30)

    # =========================================================================
    # FIELD ENCRYPTION
    #
    # FIX: Changed from plain str to SecretStr.
    # The Fernet key is a cryptographic secret Ã¢â‚¬â€ same sensitivity as the JWT key.
    # =========================================================================

    FIELD_ENCRYPTION_KEY: SecretStr = Field(
        default=SecretStr(""),
        description=(
            "Fernet key for encrypting sensitive DB columns. "
            "Leave empty to disable. "
            "Generate: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    )

    # =========================================================================
    # CORS
    # =========================================================================

    ALLOWED_ORIGINS: str = Field(default="http://localhost:3000")

    @computed_field  # type: ignore[misc]
    @property
    def ALLOWED_ORIGINS_LIST(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]


    # =========================================================================
    # CLOUDFLARE R2 / AWS S3
    # =========================================================================

    R2_ACCOUNT_ID: str = Field(default="")
    R2_ACCESS_KEY_ID: SecretStr = Field(default=SecretStr(""))
    R2_SECRET_ACCESS_KEY: SecretStr = Field(default=SecretStr(""))
    R2_BUCKET_NAME: str = Field(default="")
    R2_PUBLIC_URL: str = Field(default="")

    AWS_ACCESS_KEY_ID: SecretStr = Field(default=SecretStr(""))
    AWS_SECRET_ACCESS_KEY: SecretStr = Field(default=SecretStr(""))
    AWS_S3_BUCKET: str = Field(default="")
    AWS_S3_REGION: str = Field(default="ap-southeast-2")

    # =========================================================================
    # SENTRY
    # =========================================================================

    SENTRY_BACKEND_DSN: str = Field(default="")
    SENTRY_TRACES_SAMPLE_RATE: float = Field(default=0.1)

    # =========================================================================
    # TWILIO
    # =========================================================================

    TWILIO_ACCOUNT_SID: SecretStr = Field(default=SecretStr(""))
    TWILIO_AUTH_TOKEN: SecretStr = Field(default=SecretStr(""))
    TWILIO_PROXY_SERVICE: str = Field(default="")

    # =========================================================================
    # EMAIL
    # =========================================================================

    RESEND_API_KEY: SecretStr = Field(default=SecretStr(""))
    EMAIL_FROM: str = Field(default="noreply@localhost")

    # =========================================================================
    # RATE LIMITING
    # =========================================================================

    API_RATE_LIMIT_PER_MINUTE: int = Field(default=100)
    AUTH_MAX_ATTEMPTS: int = Field(default=5)
    AUTH_LOCKOUT_SECONDS: int = Field(default=900)

    # =========================================================================
    # BUSINESS RULES
    # =========================================================================

    JOB_POST_EXPIRY_HOURS: int = Field(default=72)
    BOOKING_ACCEPT_TIMEOUT_MINUTES: int = Field(default=30)
    PAYOUT_HOLD_HOURS: int = Field(default=48)

    # =========================================================================
    # PRODUCTION SAFETY CHECKS
    # =========================================================================

    @model_validator(mode="after")
    def validate_production(self) -> "Settings":
        """
        Hard production safety gate.

        Runs only when ENVIRONMENT == "production". Collects EVERY problem and
        raises once, so a misconfigured deploy fails fast at boot with a single
        clear message instead of silently behaving like development or crashing
        later in a confusing place.

        These checks are deliberately universal Ã¢â‚¬â€ they apply to every backend
        process (API and Celery workers).
        """
        if not self.IS_PRODUCTION:
            return self

        errors: list[str] = []

        # Ã¢â€â‚¬Ã¢â€â‚¬ JWT signing key Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        key = self.SECRET_KEY.get_secret_value()
        if len(key) < 32:
            errors.append(
                f"SECRET_KEY must be at least 32 characters (current length: {len(key)}). "
                f"Generate one with: openssl rand -base64 48"
            )

        # Ã¢â€â‚¬Ã¢â€â‚¬ Error monitoring Ã¢â‚¬â€ mandatory in production Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        if not self.SENTRY_BACKEND_DSN:
            errors.append(
                "SENTRY_BACKEND_DSN is required in production "
                "(without it, production errors are invisible)."
            )

        # Ã¢â€â‚¬Ã¢â€â‚¬ CORS allow-list Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        if "localhost" in self.ALLOWED_ORIGINS or "127.0.0.1" in self.ALLOWED_ORIGINS:
            errors.append(
                "ALLOWED_ORIGINS must not contain localhost/127.0.0.1 in production. "
                "Set it to your real frontend origin, e.g. https://app.yourdomain.com"
            )


        # Ã¢â€â‚¬Ã¢â€â‚¬ Debug output must be off Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        if self.DEBUG:
            errors.append(
                "DEBUG must be false in production Ã¢â‚¬â€ it exposes internal error detail."
            )

        # Ã¢â€â‚¬Ã¢â€â‚¬ Database must be a real, non-local DSN Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        if "localhost" in self.DATABASE_URL or "127.0.0.1" in self.DATABASE_URL:
            errors.append(
                "DATABASE_URL points at localhost/127.0.0.1 Ã¢â‚¬â€ not valid for a "
                "production deployment."
            )

        if errors:
            raise ValueError(
                "Production configuration is invalid Ã¢â‚¬â€ refusing to start:\n  - "
                + "\n  - ".join(errors)
            )

        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
