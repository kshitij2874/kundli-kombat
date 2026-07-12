from functools import lru_cache

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_sol_model: str = Field(default="gpt-5.6-sol", alias="OPENAI_SOL_MODEL")
    openai_mini_model: str = Field(default="gpt-5-mini", alias="OPENAI_MINI_MODEL")
    langfuse_public_key: str | None = Field(default=None, alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str | None = Field(default=None, alias="LANGFUSE_SECRET_KEY")
    langfuse_host: AnyHttpUrl | None = Field(default=None, alias="LANGFUSE_HOST")
    elevenlabs_api_key: str | None = Field(default=None, alias="ELEVENLABS_API_KEY")
    linkup_api_key: str | None = Field(default=None, alias="LINKUP_API_KEY")
    dodo_api_key: str | None = Field(default=None, alias="DODO_API_KEY")
    convex_url: AnyHttpUrl | None = Field(default=None, alias="CONVEX_URL")
    convex_deploy_key: str | None = Field(default=None, alias="CONVEX_DEPLOY_KEY")
    web_origin: str = Field(default="http://localhost:5173", alias="WEB_ORIGIN")

    @property
    def langfuse_configured(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key and self.langfuse_host)

    @property
    def agency_configured(self) -> bool:
        return bool(self.openai_api_key and self.langfuse_configured)


@lru_cache
def get_settings() -> Settings:
    return Settings()
