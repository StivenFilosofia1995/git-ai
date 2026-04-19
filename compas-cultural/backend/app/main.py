from contextlib import asynccontextmanager
import os
import sys
import traceback
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Print startup info immediately
print("=" * 50)
print("🚀 Cultura ETÉREA API — Starting up")
print(f"   Python: {sys.version}")
print(f"   CWD: {os.getcwd()}")
print("=" * 50)

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    print("✅ slowapi imported")
except Exception as e:
    print(f"⚠️  slowapi import failed: {e}")
    # Create dummy objects so app still starts
    Limiter = None

try:
    from app.config import settings
    print(f"✅ Config loaded — supabase_url={settings.supabase_url[:30] if settings.supabase_url else '(empty)'}...")
    print(f"   CORS origins: {settings.effective_cors_origins}")
    if not settings.supabase_url:
        print("⚠️  SUPABASE_URL not set — data endpoints will fail")
    if not settings.anthropic_api_key:
        print("⚠️  ANTHROPIC_API_KEY not set — chat will use fallback")
except Exception as e:
    print(f"❌ Config FAILED: {e}")
    traceback.print_exc()
    raise

if Limiter:
    limiter = Limiter(key_func=get_remote_address)
else:
    limiter = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🚀 Starting Cultura ETÉREA API")
    try:
        print(f"   CORS origins: {settings.effective_cors_origins}")
        print(f"   Frontend URL: {settings.frontend_url}")
        print(f"   Supabase URL: {settings.supabase_url[:40]}...")
    except Exception as e:
        print(f"⚠️  Config print failed: {e}")

    try:
        from app.database import supabase
        result = supabase.table("lugares").select("id", count="exact").limit(1).execute()
        print(f"✅ Conectado a Supabase — {result.count} lugares en BD")
    except Exception as e:
        print(f"⚠️  Supabase check failed (app continues): {e}")

    try:
        if os.getenv("DISABLE_SCHEDULER", "").lower() not in ("1", "true"):
            from app.scheduler import start_scheduler
            start_scheduler()
        else:
            print("⏸  Scheduler disabled via DISABLE_SCHEDULER env var")
    except Exception as e:
        print(f"⚠️  Scheduler failed to start (app continues): {e}")

    yield

    try:
        from app.scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass


app = FastAPI(
    title="Cultura ETÉREA API",
    description="API para el descubrimiento cultural en tiempo real del Valle de Aburrá",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.effective_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if limiter:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

try:
    from app.api.router import api_router
    app.include_router(api_router, prefix="/api/v1")
    print("✅ API routes loaded")
except Exception as e:
    print(f"❌ API routes FAILED: {e}")
    traceback.print_exc()


@app.get("/")
async def root():
    """Serve frontend index.html if available, otherwise API info."""
    static_dir = Path(__file__).parent.parent / "static"
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"service": "Cultura ETÉREA API", "version": "1.0.0", "docs": "/docs", "health": "/health"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# SPA fallback: serve index.html for any 404 that is not an API route
from fastapi.responses import JSONResponse as _JSONResponse

@app.exception_handler(404)
async def spa_404_handler(request: Request, exc):
    # Keep JSON 404 for API paths
    if request.url.path.startswith("/api/"):
        return _JSONResponse({"detail": "Not Found"}, status_code=404)
    # Serve SPA index.html for all other 404s (React Router routes)
    _static = Path(__file__).parent.parent / "static"
    _index = _static / "index.html"
    if _index.exists():
        return FileResponse(_index)
    return _JSONResponse({"detail": "Not Found"}, status_code=404)

# Serve frontend static assets (JS, CSS, images, fonts)
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )