from fastapi import APIRouter

from app.api import espacios, eventos, busqueda, chat, zonas, health, registro, auth, scraper, perfil

api_router = APIRouter()

api_router.include_router(espacios.router, prefix="/espacios", tags=["espacios"])
api_router.include_router(eventos.router, prefix="/eventos", tags=["eventos"])
api_router.include_router(busqueda.router, prefix="/busqueda", tags=["busqueda"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(zonas.router, prefix="/zonas", tags=["zonas"])
api_router.include_router(registro.router, prefix="/registro", tags=["registro"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(perfil.router, prefix="/perfil", tags=["perfil"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(scraper.router, tags=["scraper"])