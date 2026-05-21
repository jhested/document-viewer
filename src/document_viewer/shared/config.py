"""Application configuration loaded from environment variables."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Auth
    jwt_algorithm: Literal["HS256", "RS256"] = "RS256"
    jwt_hmac_secret: SecretStr = SecretStr("")
    jwt_public_key: SecretStr = SecretStr("")
    jwt_required_iss: str | None = None

    # Redis
    redis_url: str

    # Source
    source_backend: Literal["s3", "fs"]
    s3_endpoint: str | None = None
    s3_bucket: str | None = None
    s3_region: str = "us-east-1"
    s3_access_key_id: SecretStr | None = None
    s3_secret_access_key: SecretStr | None = None
    fs_root: str = "/tmp/docs"  # noqa: S108  # dev default; production must override

    # Worker
    gotenberg_url: str = "http://gotenberg:3000"
    worker_concurrency: int = 4

    # Limits
    max_source_bytes: int = 100 * 1024 * 1024
    max_pages: int = 500
    max_page_width: int = 2400
    render_timeout_seconds: int = 30
    office_timeout_seconds: int = 60

    # Cache
    cache_ttl_seconds: int = 900

    # Rate limit (per jti, soft cap; <= 0 disables — ingress is the primary control)
    rate_limit_per_jti: int = 0
    rate_limit_window_seconds: int = 900

    # Watermark
    watermark_opacity: float = 0.18
    watermark_font_size: int = 24
    watermark_angle: float = -30.0
    watermark_color: str = "#808080"

    # Allowlist
    allowed_mimes: list[str] = Field(
        default_factory=lambda: [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.oasis.opendocument.text",
            "application/vnd.oasis.opendocument.spreadsheet",
            "application/vnd.oasis.opendocument.presentation",
            "application/rtf",
            "image/png",
            "image/jpeg",
            "image/webp",
            "image/heic",
            "image/tiff",
            "image/gif",
        ]
    )
