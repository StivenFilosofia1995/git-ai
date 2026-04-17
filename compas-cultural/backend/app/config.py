from pydantic_settings import BaseSettings
from typing import List
import secrets


class Settings(BaseSettings):
    # General
    app_env: str = "development"

    # API Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Frontend URL (for emails, CORS, etc.)
    frontend_url: str = "http://localhost:5173"

    # Supabase
    supabase_url: str
    supabase_key: str

    # Anthropic (Claude)
    anthropic_api_key: str
    anthropic_model: str = "claude-sonnet-4-20250514"

    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:5173", "http://localhost:5174"]

    # Rate limiting
    rate_limit_per_minute: int = 60

    # Scraper API key (protects /scraper/* endpoints)
    scraper_api_key: str = secrets.token_urlsafe(32)

    # SMTP
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_name: str = "Cultura ETÉREA"
    smtp_from_email: str = ""

    # Meta (Instagram/Facebook) Graph API
    meta_access_token: str = ""
    meta_ig_business_account_id: str = ""

    class Config:
        env_file = ".env"


settings = Settings()