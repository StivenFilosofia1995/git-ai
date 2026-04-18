from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import settings

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.scheduler import start_scheduler, stop_scheduler
    try:
        from app.database import supabase
        result = supabase.table("lugares").select("id", count="exact").limit(1).execute()
        print(f"✅ Conectado a Supabase — {result.count} lugares en BD")
    except Exception as e:
        print(f"⚠️  Supabase check failed (app continues): {e}")
    try:
        import os
        if os.getenv("DISABLE_SCHEDULER", "").lower() not in ("1", "true"):
            start_scheduler()
        else:
            print("⏸  Scheduler disabled via DISABLE_SCHEDULER env var")
    except Exception as e:
        print(f"⚠️  Scheduler failed to start (app continues): {e}")
    yield
    try:
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

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

from app.api.router import api_router  # noqa: E402

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )