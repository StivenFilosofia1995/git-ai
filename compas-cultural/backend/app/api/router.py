from fastapi import APIRouter
import traceback

api_router = APIRouter()

# Load each route module independently so one failure doesn't break everything
_route_modules = [
    ("app.api.espacios", "/espacios", "espacios"),
    ("app.api.eventos", "/eventos", "eventos"),
    ("app.api.busqueda", "/busqueda", "busqueda"),
    ("app.api.chat", "/chat", "chat"),
    ("app.api.zonas", "/zonas", "zonas"),
    ("app.api.registro", "/registro", "registro"),
    ("app.api.auth", "/auth", "auth"),
    ("app.api.perfil", "/perfil", "perfil"),
    ("app.api.resenas", "/resenas", "resenas"),
    ("app.api.health", "/health", "health"),
    ("app.api.scraper", "", "scraper"),
]

for module_path, prefix, tag in _route_modules:
    try:
        import importlib
        mod = importlib.import_module(module_path)
        api_router.include_router(mod.router, prefix=prefix, tags=[tag])
    except Exception as e:
        print(f"⚠️  Failed to load route {module_path}: {e}")
        traceback.print_exc()