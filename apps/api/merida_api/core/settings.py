from pathlib import Path
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

    capture_token: str = "local-capture-token"
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

    @property
    def notion_configured(self) -> bool:
        return all(
            (
                self.notion_token,
                self.notion_database_id,
                self.notion_resume_database_id,
                self.notion_notes_database_id,
            )
        )

    @property
    def deepseek_configured(self) -> bool:
        return bool(self.deepseek_api_key)
