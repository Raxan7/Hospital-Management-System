from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./onehms.db"
    jwt_secret: str = "dev-secret-change-me-use-at-least-32-bytes"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 720
    cors_origins: str = "http://localhost:8082"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
