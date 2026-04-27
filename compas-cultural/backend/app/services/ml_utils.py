"""
ml_utils.py — Primitivas matemáticas compartidas para scoring ML.

Módulos:
  - BM25 multi-campo (búsqueda relevante)
  - Decaimiento exponencial (time decay de interacciones)
  - Haversine km (proximidad geográfica)
  - Wilson lower bound (ranking de reseñas bayesiano)
  - softmax_normalize (normalización de scores)
  - Proceso de Poisson (scheduling de scraping)
  - activity_to_numeric (nivel de actividad → score)
  - log1p_score (popularidad saturante)

Sin dependencias externas — solo stdlib math.
"""
from __future__ import annotations

import math
import unicodedata
from typing import Sequence

_LN2 = math.log(2)

# ─────────────────────────────────────────────────────────────
# Tokenización compartida
# ─────────────────────────────────────────────────────────────

def tokenize(text: str) -> list[str]:
    """
    Tokeniza texto en minúsculas, sin acentos, solo alfanumérico.
    Filtra tokens de longitud < 2.
    """
    if not text:
        return []
    norm = unicodedata.normalize("NFD", text.lower())
    clean = "".join(c if c.isalnum() or c == " " else " " for c in norm
                    if unicodedata.category(c) != "Mn")
    return [t for t in clean.split() if len(t) >= 2]


# ─────────────────────────────────────────────────────────────
# BM25 — relevancia de búsqueda
# ─────────────────────────────────────────────────────────────

def bm25_score(
    query_tokens: list[str],
    field_tokens: list[str],
    *,
    k1: float = 1.5,
    b: float = 0.75,
    avg_doc_len: float = 50.0,
) -> float:
    """
    BM25 para un solo campo.

    BM25(q,d) = Σ_t [ IDF(t) * tf(t,d)*(k1+1) / (tf(t,d) + k1*(1-b+b*|d|/avgdl)) ]

    IDF simplificado = ln2 por término coincidente (sin corpus completo).
    k1=1.5 → saturación moderada de frecuencia de término.
    b=0.75  → penalización por longitud del documento.
    """
    if not query_tokens or not field_tokens:
        return 0.0

    tf_map: dict[str, int] = {}
    for tok in field_tokens:
        tf_map[tok] = tf_map.get(tok, 0) + 1

    doc_len = len(field_tokens)
    score = 0.0
    for qt in query_tokens:
        tf = tf_map.get(qt, 0)
        if tf == 0:
            continue
        numerator = tf * (k1 + 1)
        denominator = tf + k1 * (1.0 - b + b * doc_len / avg_doc_len)
        score += _LN2 * numerator / denominator
    return score


def multi_field_bm25(
    query_tokens: list[str],
    fields: dict[str, tuple[str, float]],
    avg_doc_len: float = 50.0,
) -> float:
    """
    BM25 sobre múltiples campos con pesos por campo.

    fields = {
        "nombre":      ("El Teatro Pablo Tobón Uribe", 3.0),
        "barrio":      ("Aranjuez",                   1.5),
        "descripcion": ("Festival de jazz ...",        1.0),
    }

    Retorna score agregado ponderado.
    """
    total = 0.0
    for _name, (text, weight) in fields.items():
        tokens = tokenize(text or "")
        total += weight * bm25_score(query_tokens, tokens, avg_doc_len=avg_doc_len)
    return total


# ─────────────────────────────────────────────────────────────
# Time Decay — interacciones y urgencia
# ─────────────────────────────────────────────────────────────

def exponential_decay(t_days: float, half_life: float = 14.0) -> float:
    """
    Decaimiento exponencial: e^(-ln2 * t / t_half).

    t=0       → 1.0
    t=t_half  → 0.5
    t=2*t_half→ 0.25

    half_life=14d → preferencias de 2 semanas pesan 50% de hoy.
    """
    return math.exp(-_LN2 * max(0.0, t_days) / half_life)


def urgency_score(days_until: float, weight: float = 4.0, decay: float = 3.0) -> float:
    """
    Score de urgencia para un evento.
    urgency = weight * e^(-days_until / decay)

    days_until=0 (hoy) → weight (4.0)
    days_until=3        → weight/e ≈ 1.47
    days_until=7        → weight*e^(-7/3) ≈ 0.42
    """
    return weight * math.exp(-max(0.0, days_until) / decay)


# ─────────────────────────────────────────────────────────────
# Haversine — distancia geográfica
# ─────────────────────────────────────────────────────────────

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia del gran círculo en km (fórmula de Haversine)."""
    R = 6371.0
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlng / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def geo_score(dist_km: float, sigma_km: float = 5.0, weight: float = 5.0) -> float:
    """
    Score de proximidad geográfica.
    geo = weight * e^(-dist_km / sigma_km)

    dist=0km  → weight (5.0)
    dist=5km  → weight/e ≈ 1.84
    dist=20km → ~0.08
    """
    return weight * math.exp(-max(0.0, dist_km) / sigma_km)


# ─────────────────────────────────────────────────────────────
# Popularidad — log saturante
# ─────────────────────────────────────────────────────────────

def log1p_score(x: float, cap: float = 5.0) -> float:
    """
    Score de popularidad: log(1+x), acotado a cap.
    Evita que un evento viral domine completamente.
    """
    return min(cap, math.log1p(max(0.0, x)))


# ─────────────────────────────────────────────────────────────
# Calidad de contenido
# ─────────────────────────────────────────────────────────────

def quality_score(item: dict) -> float:
    """
    Score de calidad del contenido de un evento/espacio.
    Máximo teórico: 4.0

      +1.0  tiene imagen
      +0.5  es gratuito (más accesible)
      +1.0  tiene descripción ≥ 50 chars
      +0.5  descripción ≥ 150 chars (detallada)
      +0.5  tiene dirección exacta
      +0.5  verificado / nivel_actividad activo
    """
    score = 0.0
    if item.get("imagen_url"):
        score += 1.0
    if item.get("es_gratuito"):
        score += 0.5
    desc = item.get("descripcion") or item.get("descripcion_corta") or ""
    if len(desc) >= 50:
        score += 1.0
    if len(desc) >= 150:
        score += 0.5
    if item.get("direccion"):
        score += 0.5
    if item.get("verificado") or item.get("nivel_actividad") in ("muy_activo", "activo"):
        score += 0.5
    return score


# ─────────────────────────────────────────────────────────────
# Nivel de actividad → numérico
# ─────────────────────────────────────────────────────────────

def activity_to_numeric(nivel: str | None) -> float:
    """
    Mapea nivel_actividad string → score numérico [0..4].
    Usado para rankear espacios por actividad.
    """
    tabla = {
        "muy_activo": 4.0,
        "activo":     2.5,
        "regular":    1.5,
        "inactivo":   0.5,
        "cerrado":    0.0,
    }
    return tabla.get((nivel or "").lower(), 1.0)


# ─────────────────────────────────────────────────────────────
# Wilson Score — ranking bayesiano de reseñas
# ─────────────────────────────────────────────────────────────

def wilson_lower_bound(n_pos: int, n_total: int, confidence: float = 0.95) -> float:
    """
    Límite inferior del intervalo de confianza de Wilson para proporción binomial.
    z=1.96 para 95% CI.

    Caso de uso: rankear items con pocas reseñas vs. muchas.
    - 5/5 estrellas con 2 votos → score bajo (poca evidencia)
    - 4.2/5 con 100 votos → score alto (mucha evidencia)

    Retorna valor en [0,1].
    """
    if n_total == 0:
        return 0.0
    z = 1.96  # 95% CI
    p = n_pos / n_total
    denom = 1.0 + z * z / n_total
    centre = p + z * z / (2.0 * n_total)
    margin = z * math.sqrt(p * (1.0 - p) / n_total + z * z / (4.0 * n_total * n_total))
    return (centre - margin) / denom


def bayesian_average(
    puntuaciones: list[int | float],
    *,
    prior_n: int = 5,
    prior_mean: float = 3.5,
) -> float:
    """
    Media bayesiana con prior.

    bayesian_avg = (C * m + Σ_i r_i) / (C + n)

    C = prior_n  (votos del prior, default 5)
    m = prior_mean (media del prior, default 3.5 / 5)
    n = número de reseñas reales
    r_i = puntuación individual

    Evita que 1 reseña perfecta infle el score.
    Con pocos votos, el resultado se acerca al prior (3.5).
    Con muchos votos, converge a la media real.
    """
    n = len(puntuaciones)
    if n == 0:
        return prior_mean
    total = sum(puntuaciones)
    return (prior_n * prior_mean + total) / (prior_n + n)


# ─────────────────────────────────────────────────────────────
# Proceso de Poisson — scheduling de scraping
# ─────────────────────────────────────────────────────────────

def poisson_prob_new_event(lambda_diaria: float, window_hours: float = 6.0) -> float:
    """
    P(≥1 evento nuevo en window_hours) bajo proceso de Poisson.

    P = 1 - e^(-λ * t)    donde t = window_hours / 24

    λ=1/día, 6h → P≈22%
    λ=3/día, 6h → P≈53%
    λ=7/día, 6h → P≈84%
    """
    t = window_hours / 24.0
    return 1.0 - math.exp(-max(0.0, lambda_diaria) * t)


# ─────────────────────────────────────────────────────────────
# Normalización
# ─────────────────────────────────────────────────────────────

def softmax_normalize(scores: Sequence[float]) -> list[float]:
    """
    Softmax numéricamente estable.
    Convierte scores crudos en probabilidades [0,1] que suman 1.
    Útil para mostrar confianza normalizada en el frontend.
    """
    if not scores:
        return []
    max_s = max(scores)
    exp_s = [math.exp(s - max_s) for s in scores]
    total = sum(exp_s)
    return [e / total for e in exp_s]


def min_max_normalize(scores: Sequence[float]) -> list[float]:
    """
    Min-max normalization a [0,1].
    Preserva orden; no asume distribución.
    """
    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if hi == lo:
        return [1.0] * len(scores)
    return [(s - lo) / (hi - lo) for s in scores]
