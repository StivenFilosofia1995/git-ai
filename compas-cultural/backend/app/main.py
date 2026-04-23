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
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    from app.limiter import limiter
    print("✅ slowapi imported")
except Exception as e:
    print(f"⚠️  slowapi import failed: {e}")
    _rate_limit_exceeded_handler = None
    RateLimitExceeded = None
    SlowAPIMiddleware = None
    limiter = None

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

STATIC_DIR = Path(__file__).parent.parent / "static"


def _resolve_static_file(request_path: str) -> Path | None:
    """Resolve a non-API URL path to a safe file under static dir."""
    clean = (request_path or "").lstrip("/")
    if not clean:
        return None

    # Prevent path traversal and absolute paths.
    if ".." in clean or clean.startswith("/") or clean.startswith("\\"):
        return None

    candidate = (STATIC_DIR / clean).resolve()
    try:
        candidate.relative_to(STATIC_DIR.resolve())
    except Exception:
        return None

    if candidate.exists() and candidate.is_file():
        return candidate
    return None

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.effective_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if limiter and RateLimitExceeded and _rate_limit_exceeded_handler and SlowAPIMiddleware:
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
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"service": "Cultura ETÉREA API", "version": "1.0.0", "docs": "/docs", "health": "/health"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# ── Error handlers ────────────────────────────────────────────────────────
from fastapi.responses import JSONResponse as _JSONResponse
from fastapi.exceptions import RequestValidationError


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Devuelve mensajes legibles para errores de validación (422)."""
    messages = [
        f"{'.'.join(str(l) for l in e['loc'])}: {e['msg']}"
        for e in exc.errors()
    ]
    return _JSONResponse(
        status_code=422,
        content={"detail": "Datos inválidos", "errors": messages},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Captura cualquier excepción no controlada en rutas /api/ y retorna JSON."""
    if request.url.path.startswith("/api/"):
        print(f"[ERROR 500] {request.method} {request.url.path} — {type(exc).__name__}: {exc}")
        return _JSONResponse(
            status_code=500,
            content={"detail": "Error interno del servidor. Intenta de nuevo más tarde."},
        )
    # Para rutas no-API, dejar que FastAPI maneje normalmente
    raise exc


# SPA fallback: serve index.html for any 404 that is not an API route
@app.exception_handler(404)
async def spa_404_handler(request: Request, exc):
    # Keep JSON 404 for API paths
    if request.url.path.startswith("/api/"):
        return _JSONResponse({"detail": "Not Found"}, status_code=404)

    # If it's a real static file request, serve file or return 404 (not SPA HTML).
    if "." in request.url.path.rsplit("/", 1)[-1]:
        static_file = _resolve_static_file(request.url.path)
        if static_file:
            return FileResponse(static_file)
        return _JSONResponse({"detail": "Not Found"}, status_code=404)

    # Serve SPA index.html for all other 404s (React Router routes)
    _index = STATIC_DIR / "index.html"
    if _index.exists():
        return FileResponse(_index)
    return _JSONResponse({"detail": "Not Found"}, status_code=404)

# Serve frontend static assets (JS, CSS, images, fonts)
# NOTE: Mount at /assets to avoid intercepting /health and /api routes.
# The SPA fallback (404 handler above) serves index.html for all other paths.
if STATIC_DIR.exists():
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend-assets")
    # Also mount icons, fonts, etc.
    for subdir in ["icons", "fonts", "images"]:
        sub_path = STATIC_DIR / subdir
        if sub_path.exists():
            app.mount(f"/{subdir}", StaticFiles(directory=str(sub_path)), name=f"frontend-{subdir}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )