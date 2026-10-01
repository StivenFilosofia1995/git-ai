"""Facebook con la sesión del usuario: pestaña de eventos de las páginas de espacios/colectivos.

Facebook ofusca el HTML, así que se usa lo estable: los links /events/<id>, las
etiquetas og:* y el texto visible de la página del evento, con un parser de
fechas determinista (español e inglés, según el idioma de la cuenta).
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from runner.browser import pausa, verificar_sesion

CO_TZ = ZoneInfo("America/Bogota")
_MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
          "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
          "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8, "sep": 9, "sept": 9,
          "oct": 10, "nov": 11, "dic": 12,
          "january": 1, "february": 2, "march": 3, "april": 4, "june": 6, "july": 7, "august": 8,
          "september": 9, "october": 10, "november": 11, "december": 12,
          "jan": 1, "apr": 4, "aug": 8, "dec": 12}
_MES_RE = "|".join(sorted(_MESES, key=len, reverse=True))

# "sábado, 3 de octubre de 2026 de 20:00 a 23:00" | "SÁB, 3 OCT A LAS 20:00" | "3 de octubre a las 8 p. m."
_ES_RE = re.compile(
    rf"(\d{{1,2}})\s+(?:de\s+)?({_MES_RE})\.?(?:\s+(?:de\s+)?(\d{{4}}))?"
    r"(?:[^\d]{0,12}?(\d{1,2})(?::(\d{2}))?\s*(a\.?\s?m\.?|p\.?\s?m\.?)?)?"
)
# "Saturday, October 3, 2026 at 8 PM" | "Oct 3 at 8:00 PM"
_EN_RE = re.compile(
    rf"({_MES_RE})\.?\s+(\d{{1,2}})(?:,?\s+(\d{{4}}))?(?:\s+at\s+(\d{{1,2}})(?::(\d{{2}}))?\s*(am|pm)?)?",
)


def _sin_tildes(s: str) -> str:
    return unicodedata.normalize("NFD", s.lower()).encode("ascii", "ignore").decode()


def parsear_fecha_fb(texto: str, ahora: Optional[datetime] = None) -> tuple[Optional[datetime], bool]:
    """Devuelve (fecha en Bogotá, hora_confirmada). Sin año → el próximo que no haya pasado."""
    ahora = ahora or datetime.now(CO_TZ)
    t = _sin_tildes(texto)
    for rx, orden in ((_ES_RE, "es"), (_EN_RE, "en")):
        m = rx.search(t)
        if not m:
            continue
        if orden == "es":
            dia, mes_txt, anio, hh, mm, ampm = m.groups()
        else:
            mes_txt, dia, anio, hh, mm, ampm = m.groups()
        mes = _MESES.get(mes_txt.rstrip("."))
        if not mes:
            continue
        try:
            d = int(dia)
            y = int(anio) if anio else ahora.year
            h = int(hh) if hh else 0
            mi = int(mm) if mm else 0
            if ampm:
                pm = ampm.replace(".", "").replace(" ", "").startswith("p")
                if pm and h < 12:
                    h += 12
                if not pm and h == 12:
                    h = 0
            if h > 23 or mi > 59:
                h, mi = 0, 0
                hh = None
            dt = datetime(y, mes, d, h, mi, tzinfo=CO_TZ)
            if not anio and dt.date() < ahora.date():
                dt = dt.replace(year=y + 1)
            return dt, bool(hh)
        except ValueError:
            continue
    return None, False


async def _meta(page, prop: str) -> Optional[str]:
    try:
        return await page.get_attribute(f'meta[property="{prop}"]', "content", timeout=3000)
    except Exception:
        return None


async def eventos_de_pagina(ctx, url_pagina: str, max_eventos: int = 8) -> list[dict]:
    """Lee la pestaña de eventos próximos de una página de Facebook."""
    base = url_pagina.rstrip("/")
    if not base.startswith("http"):
        base = f"https://www.facebook.com/{base.lstrip('@/')}"
    page = await ctx.new_page()
    eventos: list[dict] = []
    try:
        await page.goto(f"{base}/upcoming_hosted_events", wait_until="domcontentloaded", timeout=45_000)
        verificar_sesion(page.url, "fb")
        await pausa(3, 6)
        await page.mouse.wheel(0, 1800)
        await pausa(2, 4)
        hrefs = await page.eval_on_selector_all(
            'a[href*="/events/"]', "els => els.map(e => e.href)")
        ids, links = set(), []
        for h in hrefs:
            m = re.search(r"/events/(\d{6,})", h)
            if m and m.group(1) not in ids:
                ids.add(m.group(1))
                links.append(f"https://www.facebook.com/events/{m.group(1)}/")
        for link in links[:max_eventos]:
            await pausa(3, 7)
            await page.goto(link, wait_until="domcontentloaded", timeout=45_000)
            verificar_sesion(page.url, "fb")
            await pausa(2, 4)
            titulo = (await _meta(page, "og:title")) or (await page.title())
            imagen = await _meta(page, "og:image")
            desc = (await _meta(page, "og:description")) or ""
            visible = await page.inner_text("body")
            # La fecha está en las primeras líneas visibles del evento
            cabecera = "\n".join(visible.splitlines()[:40])
            fecha, hora_ok = parsear_fecha_fb(cabecera)
            if not fecha:
                fecha, hora_ok = parsear_fecha_fb(desc)
            if not fecha or not titulo:
                continue
            eventos.append({
                "titulo": titulo.strip(), "fecha_inicio": fecha.isoformat(), "hora_confirmada": hora_ok,
                "descripcion": desc.strip() or None, "imagen_url": imagen, "fuente_url": link,
                "fuente_post_id": link.rstrip("/").rsplit("/", 1)[-1],
            })
    finally:
        await page.close()
    return eventos
