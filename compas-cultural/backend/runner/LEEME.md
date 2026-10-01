# Runner local — Instagram y Facebook con tu propia sesión

Corre en **tu PC** (IP residencial), no en Railway. Lee los perfiles de Instagram y las
páginas de Facebook de los espacios y colectivos registrados en Cultura Etérea, extrae
eventos con **código determinista** (cero IA, cero costo) y los pasa por la misma
**puerta de calidad** que el resto de los scrapers (`app/services/event_gate.py`).

## Instalación (una vez)

1. Doble clic en `instalar.bat` (crea `.venv`, instala Playwright y Chromium).
2. Copia `compas-cultural/backend/.env.example` a `.env` y llena:
   - `SUPABASE_URL`
   - `SUPABASE_KEY` = la **service role key** (la nueva, después de rotarla).
   El `.env` está en `.gitignore`: nunca se sube al repo.
3. Doble clic en `login_primera_vez.bat`: se abre un navegador; **inicia sesión tú** en
   Instagram y Facebook y cierra la ventana. La sesión queda en
   `%LOCALAPPDATA%\CulturaEterea\pw-profile`. El runner **nunca** ve ni guarda tu contraseña.

## Uso

| Archivo | Qué hace |
|---|---|
| `probar.bat` | Ensayo con 5 perfiles, navegador visible, **no escribe** en la base. Empieza por aquí. |
| `run_ig.bat` | Perfiles de IG de lugares/colectivos + tu feed (solo posts de cuentas conocidas). |
| `run_fb.bat` | Pestaña de eventos próximos de las páginas de Facebook registradas. |
| `run_todo.bat` | Todo lo anterior (lo que ejecuta la tarea programada). |
| `programar_tarea.bat` | Programa `run_todo.bat` a las 7:00 y 17:00 en el Programador de tareas. |

Opciones de línea de comando: `python -m runner.main --ig --feed --fb --limite 25 --dry-run --ver`.

Los resultados se ven en el Admin y en `GET /api/v1/scraper/health` (fuente `runner_local`).
Los registros de cada día quedan en `runner/logs/AAAA-MM-DD.log`.

## Cómo protege tu cuenta

- Solo lectura: no da likes, no sigue, no comenta, no envía mensajes.
- Ritmo humano: pausas aleatorias de 3 a 12 s y un máximo de 25 perfiles por corrida.
- Si Instagram o Facebook piden login o verificación (*checkpoint*), **se detiene** de
  inmediato (código de salida 2). Vuelve a ejecutar `login_primera_vez.bat`.
- **Recomendación:** usa una **cuenta secundaria** dedicada a Cultura Etérea. Los términos de
  Meta prohíben la automatización y la cuenta puede ser bloqueada.

## Privacidad

Del feed solo se usan posts de cuentas que ya son lugares o colectivos registrados en
Cultura Etérea. Los posts de cuentas personales se descartan sin guardarse.

## Qué se extrae y cómo (determinista)

- **Instagram:** se escuchan las respuestas JSON que la propia página carga
  (`web_profile_info`, feed, graphql) y se normalizan con `ig_feed_scraper._normalize_item`
  y `instagram_pw_scraper._parse_api_response`. El caption pasa por
  `ig_event_extractor` (fecha, hora y precio con reglas; el **día de la semana decide el año**:
  un post viejo que dice "sábado 30 de septiembre" se descarta).
- **Facebook:** links `/events/<id>` de la pestaña de eventos próximos + `og:title`,
  `og:image` y la fecha del texto visible, con `runner/fb.py:parsear_fecha_fb`
  (español e inglés).
- Cada evento hereda el espacio, el barrio y las coordenadas del lugar conocido, y lleva un
  slug con fecha. Luego `insertar_evento()` decide: publicar, cuarentena, duplicado o rechazar.
