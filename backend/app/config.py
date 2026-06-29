from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    use_ai_planner: bool = True
    chat_include_analysis_meta: bool = False
    ai_orchestrated_analytics_enabled: bool = False
    analytics_debug_trace: bool = False
    analytics_shadow_eval: bool = False
    jwt_secret_key: str = "change-me-in-production-use-a-random-32-byte-hex-string"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 8
    cors_origins: str = (
        "http://localhost:5173,"
        "http://localhost:5174,"
        "https://sales-dashboard-xi-hazel.vercel.app"
    )
    cookie_secure: bool = False
    cookie_samesite: str = "lax"

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="forbid",
    )


settings = Settings()
