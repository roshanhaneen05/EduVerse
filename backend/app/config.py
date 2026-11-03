from functools import lru_cache
from pathlib import Path
from typing import List, Union
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Base directory for the backend (C:\EduVerse\backend)
BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "EduVerse"
    API_V1_PREFIX: str = "/api/v1"

    # Security & JWT
    SECRET_KEY: str = "dev-secret-key-change-me-for-production-min-32-chars-long!"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    RATE_LIMITING_ENABLED: bool = True

    # Database
    DATABASE_URL: str = "sqlite:///./data/eduverse.db"
    DATA_DIR: str = "./data"
    UPLOAD_DIR: str = "./data/uploads"
    MAX_UPLOAD_SIZE_MB: int = 500
    STORAGE_PROVIDER_TYPE: str = "local"

    # CORS
    CORS_ORIGINS: Union[List[str], str] = "http://localhost:4200,http://127.0.0.1:4200"

    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    RELOAD: bool = True

    # AI Integration
    AI_PROVIDER: str = "local_fallback"

    @property
    def cors_origins_list(self) -> List[str]:
        if isinstance(self.CORS_ORIGINS, list):
            return self.CORS_ORIGINS
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Enforce strict secret entropy in production environments."""
        if self.is_production:
            if "dev-secret-key" in self.SECRET_KEY or len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "Insecure production configuration: SECRET_KEY must be a unique, high-entropy secret "
                    "at least 32 characters long in production environments."
                )
        return self

    @property
    def resolved_data_dir(self) -> Path:
        data_path = Path(self.DATA_DIR)
        if not data_path.is_absolute():
            data_path = (BACKEND_DIR / data_path).resolve()
        data_path.mkdir(parents=True, exist_ok=True)
        return data_path

    @property
    def resolved_upload_dir(self) -> Path:
        upload_path = Path(self.UPLOAD_DIR)
        if not upload_path.is_absolute():
            upload_path = (BACKEND_DIR / upload_path).resolve()
        upload_path.mkdir(parents=True, exist_ok=True)
        return upload_path

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def resolved_database_url(self) -> str:
        # If SQLite relative URL, ensure target data directory exists and build path
        if self.DATABASE_URL.startswith("sqlite:///./") or self.DATABASE_URL.startswith("sqlite:///data/"):
            db_filename = Path(self.DATABASE_URL.replace("sqlite:///", "")).name
            db_full_path = self.resolved_data_dir / db_filename
            return f"sqlite:///{db_full_path.as_posix()}"
        return self.DATABASE_URL


@lru_cache()
def get_settings() -> Settings:
    return Settings()

