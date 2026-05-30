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

    wechat_api_base_url: str = "https://api.weixin.qq.com"

    bilibili_passport_base: str = "https://passport.bilibili.com"
    bilibili_member_base: str = "https://member.bilibili.com"
    bilibili_api_base_url: str = "https://api.bilibili.com"
    bilibili_preupload_path: str = "/x/vu/client/preupload"
    bilibili_cover_upload_path: str = "/x/vu/client/cover/up"
    bilibili_video_submit_path: str = "/x/vu/client/add"
    bilibili_video_status_path: str = "/x/vu/client/archive/status"
    bilibili_video_delete_path: str = "/x/vu/client/archive/delete"

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )
    cors_origin_regex: str = r"^http://(localhost|127\.0\.0\.1):517[3-9]$"
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
