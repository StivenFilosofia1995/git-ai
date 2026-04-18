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
    # In Railway: set FRONTEND_URL=https://your-frontend.up.railway.app
    frontend_url: str = "http://localhost:5173"

    # Supabase
    supabase_url: str
    supabase_key: str

    # Anthropic (Claude)
    anthropic_api_key: str
    anthropic_model: str = "claude-sonnet-4-20250514"

    # CORS — base list; FRONTEND_URL is always added automatically
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

    # Resend (alternative to SMTP — easier setup: https://resend.com)
    resend_api_key: str = ""

    # Meta (Instagram/Facebook) Graph API
    meta_access_token: str = ""
    meta_ig_business_account_id: str = ""

    @property
    def effective_cors_origins(self) -> List[str]:
        """CORS origins including FRONTEND_URL and production domains."""
        origins = list(self.cors_origins)
        # Always include production domains
        for domain in [
            self.frontend_url,
            "https://culturaetereamed.com",
            "https://www.culturaetereamed.com",
            "https://culturaeterea.up.railway.app",
        ]:
            if domain and domain not in origins:
                origins.append(domain)
        return origins

    class Config:
        env_file = ".env"


settings = Settings()