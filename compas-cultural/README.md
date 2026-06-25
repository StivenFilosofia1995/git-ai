# Cultura ETÉREA — Medellín · Valle de Aburrá

Plataforma web de descubrimiento cultural en tiempo real para el Valle de Aburrá (Medellín + 9 municipios). Integra datos estructurados de investigación, scraping automatizado y consulta asistida por IA para visibilizar todo el ecosistema cultural: institucional, independiente y underground.

## Arquitectura

- **Frontend**: React 18 + Vite + TypeScript + Tailwind CSS + Mapbox GL JS
- **Backend**: FastAPI (Python 3.11+)
- **Base de datos**: Supabase (PostgreSQL + PostGIS + pgvector)
- **Scraping**: Playwright + BeautifulSoup4 + Apify
- **IA**: Ollama local/remoto para chat y scraping (`qwen2.5:1.5b` por defecto), con soporte legado para Anthropic/Groq/Gemini
- **Deploy**: Vercel (frontend) + Railway (backend + workers)

## Instalación

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Configurar variables de entorno
uvicorn app.main:app --reload
```

### Ollama en Railway

- `OLLAMA_MODEL` debe quedar en `qwen2.5:1.5b` salvo que hayas validado otro modelo en memoria y latencia.
- `OLLAMA_BASE_URL=http://localhost:11434/v1` solo funciona si Ollama corre dentro del mismo servicio donde vive FastAPI.
- Si Ollama corre en otro servicio de Railway, usa la URL interna o pública de ese servicio en `OLLAMA_BASE_URL`.
- Podés verificar la conexión en `/api/v1/chat/test` y en `/api/v1/health`.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
# Configurar variables de entorno
npm run dev
```

## Desarrollo

Ver [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) para detalles técnicos.

## Licencia

Este proyecto es de código abierto bajo la licencia MIT.