# -*- coding: utf-8 -*-
"""
Clasificador ML de eventos culturales — LogisticRegression (scikit-learn).

Reemplaza / complementa el scorer manual de data_quality.py con un modelo
entrenado sobre eventos reales de la BD + negativos sintéticos.
"""
from __future__ import annotations

import base64
import json
import logging
import math
import re
import unicodedata
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)

# ─── Términos reutilizados de data_quality ────────────────────────────────────
_POSITIVE_TERMS = {
    "evento", "agenda", "programacion", "concierto", "recital", "obra",
    "funcion", "festival", "muestra", "taller", "charla", "conversatorio",
    "foro", "exposicion", "cine", "danza", "performance", "boletas",
    "boleteria", "entradas", "inscripcion", "cupos", "aforo",
    "en vivo", "live", "show", "presentacion", "espectaculo",
    "apertura", "clausura", "estreno", "temporada", "gira",
    "se realizara", "llevara a cabo", "invita a", "te invitamos",
    "participa en", "ven a", "asiste a", "disfruta de", "no te pierdas",
    "abierto al publico", "gratis", "gratuito", "entrada libre",
    "teatro", "galeria", "museo", "biblioteca", "circo", "hip hop",
    "jazz", "rock", "electronica", "danza", "poesia",
}

_NEGATIVE_TERMS = {
    "informo que", "segun dijo", "declaro que", "reporto que",
    "anuncio que", "publico que", "aseguro que", "manifesto que",
    "ultimas noticias", "nota de prensa", "comunicado oficial",
    "boletin de prensa", "rueda de prensa",
    "presentamos al equipo", "bienvenida al equipo", "feliz cumple",
    "pronunciamiento", "vacante de empleo", "convocatoria laboral",
    "hiring", "we are hiring", "donacion", "manifiesto politico",
    "biografia del artista", "perfil del equipo",
    "resena de", "critica de", "opinion sobre",
    "entrevista exclusiva", "behind the scenes", "asi fue como",
    "mira como", "les contamos", "te contamos", "lo que debes saber",
}

_NEGATIVE_URL_PATTERNS = (
    "/noticia", "/noticias", "/news", "/blog/", "/post/", "/comunicado",
    "/articulo", "/prensa", "/reportaje", "/cronica",
)

_SOURCE_HINTS = (
    "/event", "/agenda", "/programacion", "tuboleta", "eventbrite",
    "/actividad", "/actividades", "/funcion", "/espectaculo",
)

_TRUSTED_SOURCE_PREFIXES = (
    "comfama", "fundacion_epm", "uva_epm", "parque_deseos",
    "biblioteca_epm", "planetario_medellin", "compas_urbano", "instagram",
    "bibliotecas_mde", "precision_scraper", "admin_manual",
)

_INVITATION_SIGNALS = (
    "te invitamos", "no te pierdas", "ven a", "asiste a", "lo esperamos",
    "abierto al publico", "entrada libre", "puedes asistir",
)

_LOCATION_SIGNALS = (
    "barrio", "auditorio", "sala", "teatro", "galeria", "parque",
    "biblioteca", "museo", "centro cultural", "casa de la cultura",
)

_PRICE_SIGNALS = ("gratis", "gratuito", "boleta", "entrada", "boleteria", "valor")

# ─── Negativos sintéticos (noticias, comunicados, ofertas laborales) ──────────
_SYNTHETIC_NEGATIVES = [
    # Noticias políticas y sociales
    "el alcalde informo que se tomaran medidas ante la situacion de orden publico",
    "segun dijo el gobernador las obras viales avanzaran en las proximas semanas",
    "el secretario de salud declaro que la vacunacion continua sin problemas",
    "el instituto municipal reporto que los indicadores economicos mejoraron",
    "la administracion anuncio que se abriran nuevas convocatorias laborales",
    "el concejo de medellin publico que aprobaron el presupuesto del proximo ano",
    "el presidente aseguro que el pais esta en la senda correcta",
    "el ministro manifesto que las reformas generaran miles de empleos nuevos",
    "ultimas noticias de la administracion municipal sobre el plan de desarrollo",
    "nota de prensa del departamento de comunicaciones de la alcaldia",
    "comunicado oficial sobre la decision del tribunal administrativo",
    "boletin de prensa de la gobernacion de antioquia",
    "rueda de prensa para anunciar los nuevos contratos de infraestructura",
    # Recursos humanos y convocatorias laborales
    "presentamos al equipo de ventas de nuestra empresa regional",
    "bienvenida al equipo de innovacion que se une a nuestra organizacion",
    "vacante de empleo para profesionales en administracion de empresas",
    "convocatoria laboral para ingenieros de software con experiencia en java",
    "hiring senior developers for our growing tech team in medellin",
    "we are hiring data analysts to join our analytics department",
    "donacion de equipos tecnologicos para instituciones educativas publicas",
    "manifiesto politico del movimiento ciudadano ante las proximas elecciones",
    "biografia del artista y su trayectoria en las artes visuales colombianas",
    "perfil del equipo directivo de la corporacion cultural",
    # Reseñas y críticas editoriales
    "resena de la ultima novela del autor bogotano publicada este semestre",
    "critica de la pelicula ganadora del festival internacional de cine",
    "opinion sobre la gestion cultural de la administracion publica",
    "entrevista exclusiva con el director de la fundacion de artes",
    "behind the scenes del rodaje de la nueva serie de television colombiana",
    "asi fue como el colectivo artistic logro financiar su primer proyecto",
    "mira como se prepara el equipo de produccion del nuevo espectaculo",
    "les contamos todo sobre el proceso creativo del artista en residencia",
    "te contamos los detalles de la investigacion sobre patrimonio cultural",
    "lo que debes saber sobre los cambios en la legislacion cultural",
    # Noticias deportivas y de farándula
    "el equipo de futbol anuncio la contratacion de nuevos jugadores",
    "la cantante confirmo su separacion de la banda musical",
    "el actor colombiano hablo sobre su nueva pelicula en entrevista",
    "el futbolista firmo contrato con el club europeo por tres temporadas",
    "la modelo paisa fue portada de la revista de moda internacional",
    # Noticias de economía y finanzas
    "el banco central reporto que la inflacion bajo al cuatro por ciento",
    "la bolsa de valores registro su mejor semana en los ultimos meses",
    "el peso colombiano se deprecio frente al dolar en las ultimas horas",
    "las exportaciones del pais crecieron un doce por ciento segun cifras oficiales",
    "el gobierno anuncio nuevos incentivos tributarios para el sector productivo",
    # Noticias de orden público
    "las autoridades capturaron a los responsables del robo en el norte de la ciudad",
    "la policia reporto que los indices de criminalidad bajaron en el primer trimestre",
    "el ejercito incauto un cargamento de sustancias ilicitas en el bajo cauca",
    "la fiscalia abrio investigacion formal contra el funcionario por irregularidades",
    # Comunicados institucionales
    "el ministerio de educacion informo cambios en el calendario escolar",
    "el dane publico los resultados del censo de poblacion y vivienda",
    "el invias reporto el cierre temporal de la via panamericana por deslizamiento",
    "la aerocivil informo restricciones temporales en el espacio aereo nacional",
    "el instituto nacional de salud actualizo las cifras de casos de dengue",
    # Noticias tecnología y negocios
    "la empresa de tecnologia abrio nuevas oficinas en el parque tecnologico",
    "el startups colombiano recibio inversion de capital de riesgo norteamericano",
    "la plataforma de comercio electronico supero el millon de usuarios activos",
    "el ceo de la empresa renuncio tras los resultados del tercer trimestre",
    # Medioambiente y ciencia
    "los cientificos reportaron el avance del deshielo en los glaciares tropicales",
    "el estudio revelo que la contaminacion del aire aumento en las ciudades",
    "investigadores descubrieron una nueva especie de anfibio en la selva amazonica",
    "el fenomeno del nino afectara las lluvias en antioquia durante el segundo semestre",
    # Más ejemplos variados
    "el concejo aprobó en primer debate el proyecto de acuerdo sobre movilidad",
    "según el informe de gestion la entidad atendio mas de cien mil usuarios",
    "el secretario de educacion presento los resultados de las pruebas saber",
    "la fundacion reporto los avances del programa de reforestacion urbana",
    "el personero municipal advirtio sobre irregularidades en la contratacion",
    "segun cifras del dane el desempleo bajo al diez por ciento en el trimestre",
    "la alcaldia informo el cronograma de obras para el segundo semestre del año",
    "el ministro de hacienda presento el proyecto de reforma tributaria al congreso",
    "la policia metropolitana realizo operativos en los principales puntos de la ciudad",
    "el tribunal administrativo de antioquia fallo a favor de la demanda ciudadana",
    "el gobernador firmo el decreto que reglamenta la ley de presupuesto participativo",
    "la procuraduria abrio investigacion disciplinaria contra varios funcionarios",
    "el banco de la republica mantuvo inalterada la tasa de referencia en su reunion",
    "el comite directivo aprobo el plan de inversiones para la vigencia fiscal",
    "la secretaria de hacienda presento el informe de ejecucion presupuestal",
    "el consejo de gobierno analizó la situacion de orden publico en la region",
    "el superintendente informo que las investigaciones por competencia desleal continuan",
    "la defensoria del pueblo presento su informe anual sobre derechos humanos",
    "segun el reporte tecnico la estructura del puente requiere intervencion urgente",
    "el plan de desarrollo contempla inversiones en infraestructura vial y educacion",
    "la comision reguladora fijo las tarifas para el servicio de acueducto y alcantarillado",
    "el ministerio del interior convoco a los partidos politicos a una reunion urgente",
    "el tribunal de arbitramento emitio su laudo sobre el contrato de concesion vial",
    "el contralor regional presento los hallazgos del proceso auditor a la entidad",
    "la secretaria general informo el cronograma de elecciones internas del gremio",
    "el director del hospital reporto la situacion de ocupacion de camas uci",
]


def _norm(text: str) -> str:
    if not text:
        return ""
    t = unicodedata.normalize("NFD", text.lower())
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", t).strip()


def extract_features(
    titulo: Optional[str],
    descripcion: Optional[str],
    fuente_url: Optional[str] = None,
    fuente: Optional[str] = None,
) -> list[float]:
    """Return 12 numerical features for logistic regression."""
    title_n = _norm(titulo or "")
    desc_n = _norm(descripcion or "")
    url_n = _norm(fuente_url or "")
    body = f"{title_n} {desc_n}".strip()

    pos_count = sum(1 for t in _POSITIVE_TERMS if t in body)
    neg_count = sum(1 for t in _NEGATIVE_TERMS if t in body)

    has_datetime = _has_date_signal(body)
    has_src_signal = any(h in url_n for h in _SOURCE_HINTS) if url_n else 0.0
    has_cat_signal = _has_category_signal(body)
    has_neg_url = any(p in url_n for p in _NEGATIVE_URL_PATTERNS) if url_n else 0.0
    title_words = min(len(title_n.split()), 20) / 20.0
    desc_len = math.log1p(len(desc_n)) / math.log1p(500)
    has_price = float(any(s in body for s in _PRICE_SIGNALS))
    has_invite = float(any(s in body for s in _INVITATION_SIGNALS))
    has_location = float(any(s in body for s in _LOCATION_SIGNALS))
    trust_score = float(
        any((fuente or "").lower().startswith(p) for p in _TRUSTED_SOURCE_PREFIXES)
    )

    return [
        min(pos_count / 12.0, 1.0),   # f0: positive term density
        min(neg_count / 8.0, 1.0),    # f1: negative term density
        float(has_datetime),           # f2: datetime signal
        float(has_src_signal),         # f3: event-like URL
        float(has_cat_signal),         # f4: cultural category
        float(has_neg_url),            # f5: news-like URL
        title_words,                   # f6: title word count (normalised)
        min(desc_len, 1.0),            # f7: description length (log-normalised)
        has_price,                     # f8: price/free signal
        has_invite,                    # f9: invitation phrase
        has_location,                  # f10: venue/location signal
        trust_score,                   # f11: trusted source
    ]


def _has_date_signal(text: str) -> float:
    month_day = re.search(
        r"\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
        r"septiembre|octubre|noviembre|diciembre|"
        r"lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b",
        text,
    )
    time_like = re.search(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\s*([ap]m)?\b", text)
    am_pm = re.search(r"\b\d{1,2}\s*(am|pm)\b", text)
    return float(bool(month_day or time_like or am_pm))


def _has_category_signal(body: str) -> float:
    cats = {
        "teatro", "musica", "danza", "cine", "festival",
        "taller", "conferencia", "galeria", "performance", "concierto",
    }
    return float(any(c in body for c in cats))


# ─── Model persistence via config_kv ─────────────────────────────────────────

_MODEL_CACHE: dict = {}  # {"clf": LogisticRegression, "loaded_at": str}


def _kv_get(key: str) -> Optional[str]:
    try:
        from app.database import supabase
        res = supabase.table("config_kv").select("value").eq("key", key).maybe_single().execute()
        return (res.data or {}).get("value")
    except Exception as exc:
        log.debug("kv_get %s error: %s", key, exc)
        return None


def _kv_set(key: str, value: str) -> None:
    try:
        from app.database import supabase
        supabase.table("config_kv").upsert({"key": key, "value": value}).execute()
    except Exception as exc:
        log.warning("kv_set %s error: %s", key, exc)


# ─── Training data ────────────────────────────────────────────────────────────

def build_training_data():
    """
    Returns (X, y) numpy arrays.
    Positives: trusted-source events from DB.
    Negatives: synthetic news phrases + ml_training_feedback rows.
    """
    import numpy as np

    X_rows: list[list[float]] = []
    y_labels: list[int] = []

    # --- Positives from DB ---
    try:
        from app.database import supabase
        prefix_filters = list(_TRUSTED_SOURCE_PREFIXES)
        # Fetch up to 2000 events from trusted sources
        res = (
            supabase.table("eventos")
            .select("titulo, descripcion, fuente_url, fuente")
            .limit(2000)
            .execute()
        )
        rows = res.data or []
        for row in rows:
            fuente = (row.get("fuente") or "").lower()
            is_trusted = any(fuente.startswith(p) for p in prefix_filters)
            if is_trusted:
                feats = extract_features(
                    row.get("titulo"),
                    row.get("descripcion"),
                    row.get("fuente_url"),
                    fuente,
                )
                X_rows.append(feats)
                y_labels.append(1)
    except Exception as exc:
        log.warning("build_training_data: DB fetch error: %s", exc)

    # --- Negatives: synthetic ---
    for text in _SYNTHETIC_NEGATIVES:
        feats = extract_features(text, "", "https://example.com/noticia/123")
        X_rows.append(feats)
        y_labels.append(0)

    # --- Negatives from manual feedback table ---
    try:
        from app.database import supabase
        fb = (
            supabase.table("ml_training_feedback")
            .select("titulo, descripcion, fuente_url, label")
            .execute()
        )
        for row in (fb.data or []):
            feats = extract_features(
                row.get("titulo"), row.get("descripcion"), row.get("fuente_url")
            )
            X_rows.append(feats)
            y_labels.append(1 if row.get("label") else 0)
    except Exception:
        pass

    if not X_rows:
        return None, None

    return np.array(X_rows, dtype=float), np.array(y_labels, dtype=int)


# ─── Train ────────────────────────────────────────────────────────────────────

def train_classifier() -> dict:
    """
    Trains a LogisticRegression, stores weights in config_kv, returns metrics.
    """
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
    import joblib
    import io

    X, y = build_training_data()
    if X is None or len(X) < 20:
        return {"error": "Datos insuficientes para entrenar (mínimo 20 ejemplos)"}

    n_pos = int(y.sum())
    n_neg = int(len(y) - n_pos)
    log.info("Entrenando clasificador: %d positivos, %d negativos", n_pos, n_neg)

    if n_pos < 5 or n_neg < 5:
        return {"error": f"Se necesitan al menos 5 ejemplos por clase (pos={n_pos}, neg={n_neg})"}

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    clf = LogisticRegression(C=1.0, max_iter=500, random_state=42)
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    metrics = {
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "precision": round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
        "training_count": len(X_train),
        "test_count": len(X_test),
        "n_positivos": n_pos,
        "n_negativos": n_neg,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }

    # Feature importances
    feature_names = [
        "positive_terms", "negative_terms", "datetime_signal", "source_url",
        "category_signal", "negative_url", "title_words", "desc_length",
        "price_signal", "invitation_signal", "location_signal", "trusted_source",
    ]
    coefs = clf.coef_[0].tolist()
    metrics["feature_importances"] = [
        {"name": name, "weight": round(w, 4)}
        for name, w in sorted(zip(feature_names, coefs), key=lambda x: -abs(x[1]))
    ]

    # Serialise model
    buf = io.BytesIO()
    joblib.dump(clf, buf)
    model_b64 = base64.b64encode(buf.getvalue()).decode()

    _kv_set("ml_classifier_v1", model_b64)
    _kv_set("ml_classifier_metrics", json.dumps(metrics))

    # Refresh in-memory cache
    _MODEL_CACHE["clf"] = clf
    _MODEL_CACHE["loaded_at"] = metrics["trained_at"]

    log.info("Clasificador entrenado: accuracy=%.3f f1=%.3f", metrics["accuracy"], metrics["f1"])
    return metrics


# ─── Load / classify ──────────────────────────────────────────────────────────

def _load_model() -> Optional[object]:
    if "clf" in _MODEL_CACHE:
        return _MODEL_CACHE["clf"]
    try:
        import joblib, io
        b64 = _kv_get("ml_classifier_v1")
        if not b64:
            return None
        clf = joblib.load(io.BytesIO(base64.b64decode(b64)))
        _MODEL_CACHE["clf"] = clf
        _MODEL_CACHE["loaded_at"] = datetime.now(timezone.utc).isoformat()
        return clf
    except Exception as exc:
        log.debug("_load_model error: %s", exc)
        return None


def classify_event(
    titulo: Optional[str],
    descripcion: Optional[str],
    fuente_url: Optional[str] = None,
    fuente: Optional[str] = None,
) -> tuple[bool, float]:
    """
    Returns (is_event, confidence).
    Falls back to (True, 0.5) if model not loaded.
    """
    clf = _load_model()
    if clf is None:
        return True, 0.5  # no model → accept (rule-based scorer handles rejection)

    feats = extract_features(titulo, descripcion, fuente_url, fuente)
    import numpy as np
    prob = float(clf.predict_proba(np.array([feats]))[0][1])
    is_event = prob >= 0.45
    _log_prediction(titulo or "", prob, is_event)
    return is_event, prob


def _log_prediction(titulo: str, prob: float, result: bool) -> None:
    try:
        raw = _kv_get("ml_recent_predictions") or "[]"
        preds: list = json.loads(raw)
        preds.append({
            "titulo": titulo[:80],
            "prob": round(prob, 3),
            "result": result,
            "ts": datetime.now(timezone.utc).isoformat()[:19],
        })
        _kv_set("ml_recent_predictions", json.dumps(preds[-50:]))
    except Exception:
        pass


# ─── Status ───────────────────────────────────────────────────────────────────

def get_model_status() -> dict:
    raw_metrics = _kv_get("ml_classifier_metrics")
    metrics = json.loads(raw_metrics) if raw_metrics else {}
    raw_preds = _kv_get("ml_recent_predictions") or "[]"
    recent = json.loads(raw_preds)[-10:]
    return {
        "status": "trained" if metrics else "untrained",
        "trained_at": metrics.get("trained_at"),
        "training_count": metrics.get("training_count", 0),
        "n_positivos": metrics.get("n_positivos", 0),
        "n_negativos": metrics.get("n_negativos", 0),
        "metrics": {
            "accuracy": metrics.get("accuracy"),
            "precision": metrics.get("precision"),
            "recall": metrics.get("recall"),
            "f1": metrics.get("f1"),
        },
        "feature_importances": metrics.get("feature_importances", []),
        "recent_predictions": recent,
    }
