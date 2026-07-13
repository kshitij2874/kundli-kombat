from functools import lru_cache

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
        env_ignore_empty=True,
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    deepseek_api_key: str | None = Field(default=None, alias="DEEPSEEK_API_KEY")
    deepseek_base_url: AnyHttpUrl = Field(
        default="https://api.deepseek.com", alias="DEEPSEEK_BASE_URL"
    )
    deepseek_model: str = Field(default="deepseek-v4-flash", alias="DEEPSEEK_MODEL")
    langfuse_public_key: str | None = Field(default=None, alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str | None = Field(default=None, alias="LANGFUSE_SECRET_KEY")
    langfuse_host: AnyHttpUrl | None = Field(default=None, alias="LANGFUSE_HOST")
    langfuse_base_url: AnyHttpUrl | None = Field(default=None, alias="LANGFUSE_BASE_URL")
    elevenlabs_api_key: str | None = Field(default=None, alias="ELEVENLABS_API_KEY")
    elevenlabs_voice_id: str = Field(default="JBFqnCBsd6RMkjVDRZzb", alias="ELEVENLABS_VOICE_ID")
    elevenlabs_model_id: str = Field(default="eleven_flash_v2_5", alias="ELEVENLABS_MODEL_ID")
    linkup_api_key: str | None = Field(default=None, alias="LINKUP_API_KEY")
    dodo_api_key: str | None = Field(default=None, alias="DODO_API_KEY")
    convex_url: AnyHttpUrl | None = Field(default=None, alias="CONVEX_URL")
    web_origin: str = Field(default="http://localhost:5173", alias="WEB_ORIGIN")

    @property
    def langfuse_configured(self) -> bool:
        return bool(
            self.langfuse_public_key
            and self.langfuse_secret_key
            and (self.langfuse_base_url or self.langfuse_host)
        )

    @property
    def langfuse_endpoint(self) -> AnyHttpUrl | None:
        return self.langfuse_base_url or self.langfuse_host

    @property
    def agency_configured(self) -> bool:
        return bool(self.deepseek_api_key and self.langfuse_configured)


@lru_cache
def get_settings() -> Settings:
    return Settings()
