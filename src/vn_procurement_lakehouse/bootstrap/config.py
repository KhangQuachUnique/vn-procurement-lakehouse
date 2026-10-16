from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py nằm ở:
# src/vn_procurement_lakehouse/bootstrap/config.py

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    database_url: str
    bronze_base_path: Path = Path("data/bronze")

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Muasamcong API
    muasamcong_base_url: str = Field(default="https://muasamcong.mpi.gov.vn/")
    muasamcong_token: SecretStr | None = None
    muasamcong_page_size: int = Field(default=50, gt=0)

    # HTTP timeouts (seconds)
    muasamcong_connect_timeout: float = Field(default=15.0, gt=0)
    muasamcong_read_timeout: float = Field(default=45.0, gt=0)
    muasamcong_write_timeout: float = Field(default=10.0, gt=0)
    muasamcong_pool_timeout: float = Field(default=5.0, gt=0)

    # Concurrency and rate limiting
    muasamcong_workers: int = Field(default=3, ge=1)
    muasamcong_min_interval: float = Field(default=0.05, ge=0.0)

    # Connection pooling
    muasamcong_max_connections: int = Field(default=5, gt=0)
    muasamcong_max_keepalive_connections: int = Field(default=2, ge=0)

    # Retry policy
    muasamcong_retry_attempts: int = Field(default=5, ge=1)
    muasamcong_retry_base_delay: float = Field(default=2.0, ge=0)
    muasamcong_retry_max_delay: float = Field(default=45.0, ge=0)


def load_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]
