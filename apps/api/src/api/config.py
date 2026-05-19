"""API configuration via environment variables."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All settings are loaded from environment variables or .env file."""

    # Database
    database_url: str = "sqlite+aiosqlite:////data/photobooth.db"
    photos_dir: str = "/data/photos"

    # JWT
    jwt_secret: str = "CHANGE-ME-IN-PRODUCTION"
    jwt_algorithm: str = "HS256"

    # SMTP (AhaSend)
    smtp_host: str = "send.ahasend.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_from_email: str = "noreply@mycreativity.nl"
    smtp_from_name: str = "Photobooth"

    # URLs
    api_url: str = "https://photobooth-api.mycreativity.nl"
    admin_url: str = "https://photobooth-admin.mycreativity.nl"

    # Seed
    admin_email: str = "steenweg@gmail.com"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
