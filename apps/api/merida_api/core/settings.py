from pathlib import Path
import ipaddress
from typing import Literal
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        extra="ignore",
        case_sensitive=False,
    )

    capture_token: str = ""
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    web_origin: str = "http://127.0.0.1:5173"
    extension_origin: str = ""

    notion_token: str = ""
    notion_database_id: str = ""
    notion_resume_database_id: str = ""
    notion_notes_database_id: str = ""
    deepseek_api_key: str = ""
    analysis_model: str = "deepseek-v4-flash"
    resume_model: str = "deepseek-v4-pro"
    llm_input_format: Literal["json"] = "json"

    export_path: Path = REPOSITORY_ROOT / "app-data/export"
    recovery_journal_path: Path = REPOSITORY_ROOT / "app-data/recovery/effects.json"

    @field_validator(
        "export_path",
        "recovery_journal_path",
        mode="after",
    )
    @classmethod
    def resolve_repository_path(cls, value: Path) -> Path:
        return value if value.is_absolute() else (REPOSITORY_ROOT / value).resolve()

    @field_validator("api_host", mode="after")
    @classmethod
    def require_loopback_host(cls, value: str) -> str:
        host = value.strip().lower()
        if host == "localhost":
            return host
        try:
            if ipaddress.ip_address(host).is_loopback:
                return host
        except ValueError:
            pass
        raise ValueError("API_HOST must be a loopback host.")

    @property
    def capture_token_configured(self) -> bool:
        token = self.capture_token.strip()
        return bool(token and token != "local-capture-token")

    @property
    def notion_applications_configured(self) -> bool:
        return bool(self.notion_token and self.notion_database_id)

    @property
    def notion_resume_configured(self) -> bool:
        return bool(
            self.notion_analysis_configured
            and self.notion_notes_database_id
        )

    @property
    def notion_analysis_configured(self) -> bool:
        return bool(
            self.notion_applications_configured
            and self.notion_resume_database_id
        )

    @property
    def notion_configured(self) -> bool:
        return self.notion_resume_configured

    @property
    def deepseek_configured(self) -> bool:
        return bool(self.deepseek_api_key)
