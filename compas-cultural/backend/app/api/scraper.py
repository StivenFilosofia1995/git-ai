"""
Endpoints para el sistema de auto-scraping.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from app.config import settings
from app.services.auto_scraper import run_auto_scraper, scrape_single_lugar, enrich_event_images

router = APIRouter(prefix="/scraper", tags=["scraper"])


def _verify_scraper_key(x_scraper_key: str = Header(..., alias="X-Scraper-Key")):
    """Verify the scraper API key from request header."""
    if x_scraper_key != settings.scraper_api_key:
        raise HTTPException(status_code=403, detail="Invalid scraper API key")


@router.post("/run", dependencies=[Depends(_verify_scraper_key)])
async def trigger_full_scraper(
    background_tasks: BackgroundTasks,
    limit: int = Query(default=None, description="Máximo de lugares a scrapear"),
):
    """Trigger manual del auto-scraper completo (se ejecuta en background)."""
    background_tasks.add_task(run_auto_scraper, limit=limit)
    return {
        "status": "started",
        "message": f"Auto-scraper iniciado en background{f' (limit={limit})' if limit else ''}",
    }


@router.post("/lugar/{lugar_id}", dependencies=[Depends(_verify_scraper_key)])
async def trigger_lugar_scraper(lugar_id: str):
    """Scrape un lugar específico (síncrono, retorna resultados)."""
    result = await scrape_single_lugar(lugar_id)
    return result


@router.get("/log")
async def get_scraping_log(
    limit: int = Query(default=50, le=200),
):
    """Obtener log de scraping reciente."""
    from app.database import supabase
    resp = (
        supabase.table("scraping_log")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return {"logs": resp.data, "total": len(resp.data)}


@router.post("/enrich-images", dependencies=[Depends(_verify_scraper_key)])
async def trigger_enrich_images(background_tasks: BackgroundTasks):
    """Buscar og:image en fuentes y actualizar eventos sin imagen."""
    background_tasks.add_task(enrich_event_images)
    return {"status": "started", "message": "Enriquecimiento de imágenes iniciado"}
