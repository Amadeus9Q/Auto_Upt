from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Auto_Upt"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"

    database_url: str = (
        "postgresql+asyncpg://auto_upt:auto_upt@localhost:5432/auto_upt"
    )

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    openai_api_key: str = ""
    openai_model: str = "gpt-5"

    browser_headless: bool = False
    screenshot_dir: str = "storage/screenshots"
    asset_storage_dir: str = "storage/assets"
    public_base_url: str = "http://127.0.0.1:8000"

    credential_encryption_key: str = ""

    frontend_account_success_url: str = "http://127.0.0.1:5173/accounts?status=success"
    frontend_account_error_url: str = "http://127.0.0.1:5173/accounts?status=error"

    wechat_api_base_url: str = "https://api.weixin.qq.com"

    bilibili_client_id: str = ""
    bilibili_client_secret: str = ""
    bilibili_redirect_uri: str = "http://127.0.0.1:8000/api/v1/accounts/bilibili/oauth/callback"
    bilibili_authorize_url: str = "https://open.bilibili.com/oauth2/authorize"
    bilibili_token_url: str = "https://open.bilibili.com/oauth2/access_token"
    bilibili_refresh_token_url: str = "https://open.bilibili.com/oauth2/refresh_token"
    bilibili_api_base_url: str = "https://open.bilibili.com/api"
    bilibili_video_upload_path: str = "/video/upload"
    bilibili_cover_upload_path: str = "/video/cover"
    bilibili_video_submit_path: str = "/video/submit"
    bilibili_video_status_path: str = "/video/status"
    bilibili_video_delete_path: str = "/video/delete"

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )
    sql_echo: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
