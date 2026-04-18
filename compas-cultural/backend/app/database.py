from supabase import create_client, Client
from app.config import settings

if settings.supabase_url and settings.supabase_key:
    supabase: Client = create_client(settings.supabase_url, settings.supabase_key)
else:
    print("⚠️  Supabase not configured — database operations will fail")
    supabase = None  # type: ignore
