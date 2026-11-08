"""Application configuration. All secrets come from environment variables (see .env.example)."""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="BID_", extra="ignore")

    environment: str = "development"  # development | production | test
    database_url: str = "sqlite:///./bharati_dev.db"
    public_base_url: str = "http://localhost:8000"  # used to build OAuth redirect URIs
    ios_callback_scheme: str = "bharatidesk"

    # Security
    jwt_secret: str = Field(default="dev-only-change-me-0123456789abcdef", min_length=32)
    access_token_minutes: int = 30
    refresh_token_days: int = 30
    # Fernet key (urlsafe base64, 32 bytes) used to encrypt stored files and OAuth tokens.
    data_encryption_key: str = ""
    allow_registration: bool = True  # first user becomes admin; disable after setup

    # Storage
    storage_dir: str = "./data/storage"
    work_dir: str = "./data/work"
    max_file_mb: int = 200
    max_zip_depth: int = 4
    max_zip_members: int = 2000

    # AI
    # api          = this server calls the Claude API (pay per use, fully automatic)
    # claude_code  = the server makes NO AI calls; analysis is done in Claude Code under the user's
    #                Claude subscription (Max plan) via tools/bid_agent.py and the investigate-case skill
    ai_mode: str = "api"
    anthropic_api_key: str = ""  # read by SDK from ANTHROPIC_API_KEY if empty
    ai_model: str = "claude-opus-5-5"
    ai_digest_model: str = "claude-opus-5-5"  # per-document digests; set claude-sonnet-5-5 to lower cost
    ai_effort: str = "high"
    ai_server_fallback: bool = True
    ai_max_case_chars: int = 600_000  # full-text budget passed to synthesis besides digests
    ocr_engine: str = "claude_vision"  # claude_vision | tesseract | deferred | none
    llm_provider: str = "anthropic"  # anthropic | fake (tests only)

    # Connectors
    google_client_id: str = ""
    google_client_secret: str = ""
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_tenant: str = "common"
    allow_local_connector: bool = False  # dev/test only: read folders from local_connector_root
    local_connector_root: str = "./data/local_folders"

    # Jobs
    run_worker_in_process: bool = True
    job_stale_seconds: int = 300

    # Retention
    default_retention_days: int = 365

    # Reports
    soffice_path: str = "soffice"
    words_per_page: int = 300  # Times New Roman 13pt, 1.5 spacing, A4, normal margins


@lru_cache
def get_settings() -> Settings:
    return Settings()
