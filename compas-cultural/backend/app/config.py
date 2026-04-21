from pydantic_settings import BaseSettings
from typing import List, Union
import json
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

    # Supabase (required for data, but defaults allow app to start)
    supabase_url: str = ""
    supabase_key: str = ""

    # Anthropic (Claude) — only used for chat, app works without it
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-haiku-20241022"

    # CORS — accepts JSON array string or comma-separated list
    cors_origins: Union[List[str], str] = "http://localhost:3000,http://localhost:5173,http://localhost:5174"

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

    # Groq AI (fast/cheap LLM for scraping — replaces Claude for non-chat tasks)
    groq_api_key: str = ""

    # Gemini (Google AI) — primary model for user chat (free tier: 1500 req/day)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # Meta (Instagram/Facebook) Graph API
    meta_access_token: str = ""
    meta_ig_business_account_id: str = ""
    meta_app_id: str = ""
    meta_app_secret: str = ""

    @property
    def effective_cors_origins(self) -> List[str]:
        """CORS origins including FRONTEND_URL and production domains.
        Handles cors_origins as JSON array string, comma-separated string, or list.
        """
        # Parse cors_origins robustly
        raw = self.cors_origins
        if isinstance(raw, str):
            raw = raw.strip()
            if raw.startswith("["):
                try:
                    origins = json.loads(raw)
                except json.JSONDecodeError:
                    origins = [s.strip().strip('"').strip("'") for s in raw.strip("[]").split(",")]
            else:
                origins = [s.strip() for s in raw.split(",") if s.strip()]
        else:
            origins = list(raw)

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