from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    use_ai_planner: bool = True
    chat_include_analysis_meta: bool = False
    jwt_secret_key: str = "change-me-in-production-use-a-random-32-byte-hex-string"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 8

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
