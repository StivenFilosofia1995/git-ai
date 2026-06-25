-- ============================================================
-- ML Features Migration
-- Agrega las columnas y tablas necesarias para el sistema de
-- recomendación personalizado por usuario.
--
-- Matemáticas implementadas:
--   - Decaimiento exponencial (t½=14d) en interacciones
--   - Proceso de Poisson por fuente de scraping
--   - Score Haversine de proximidad geográfica
--   - Popularidad log1p de eventos en 24h
-- ============================================================

-- 1. Columna metadata en interacciones_usuario para guardar barrio/municipio
--    que alimenta el scoring de proximidad geográfica.
ALTER TABLE interacciones_usuario
  ADD COLUMN IF NOT EXISTS metadata jsonb DEFAULT '{}';

-- Índice para consultas de popularidad en 24h (muy frecuentes en scoring ML)
CREATE INDEX IF NOT EXISTS idx_interacciones_created_tipo
  ON interacciones_usuario (created_at DESC, tipo)
  WHERE tipo IN ('view_evento', 'click');

-- Índice para consultas de perfil (user_id + created_at)
CREATE INDEX IF NOT EXISTS idx_interacciones_user_created
  ON interacciones_usuario (user_id, created_at DESC);

-- 2. Columna lat/lng en perfiles_usuario para scoring Haversine
--    score_geo = 5 * e^(-distancia_km / 5)
ALTER TABLE perfiles_usuario
  ADD COLUMN IF NOT EXISTS ubicacion_lat double precision,
  ADD COLUMN IF NOT EXISTS ubicacion_lng double precision;

-- 3. Tabla de scheduling Poisson por fuente de scraping
--    λ = eventos_nuevos_últimos_7días / 7  (tasa diaria)
--    P(evento nuevo en window_h) = 1 - e^(-λ * window_h/24)
CREATE TABLE IF NOT EXISTS scraping_schedule (
  id          bigserial PRIMARY KEY,
  fuente_url  text        NOT NULL UNIQUE,
  fuente_nombre text,
  -- Proceso de Poisson: λ estimada (eventos/día) actualizada por el scheduler
  lambda_diaria double precision DEFAULT 0.5,
  -- Cuándo se scrapeó por última vez
  ultimo_scrape timestamptz,
  -- Cuántos eventos nuevos se encontraron en el último scrape
  eventos_ultimo_scrape int DEFAULT 0,
  -- Total histórico para recalcular λ
  eventos_totales int DEFAULT 0,
  -- Si la fuente está activa
  activa boolean DEFAULT true,
  created_at  timestamptz DEFAULT now(),
  updated_at  timestamptz DEFAULT now()
);

-- Función para actualizar λ después de cada scrape
CREATE OR REPLACE FUNCTION update_lambda_poisson(
  p_fuente_url text,
  p_nuevos int
) RETURNS void AS $$
DECLARE
  v_k7 int;
BEGIN
  -- λ = eventos nuevos en últimos 7 días / 7
  SELECT COUNT(*) INTO v_k7
  FROM eventos
  WHERE fuente_url = p_fuente_url
    AND created_at >= NOW() - INTERVAL '7 days';

  INSERT INTO scraping_schedule (fuente_url, lambda_diaria, ultimo_scrape, eventos_ultimo_scrape, eventos_totales)
  VALUES (p_fuente_url, (v_k7::double precision / 7.0), NOW(), p_nuevos, p_nuevos)
  ON CONFLICT (fuente_url) DO UPDATE
    SET lambda_diaria = (v_k7::double precision / 7.0),
        ultimo_scrape = NOW(),
        eventos_ultimo_scrape = p_nuevos,
        eventos_totales = scraping_schedule.eventos_totales + p_nuevos,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- 4. Vista de popularidad de eventos (últimas 24h) — usada por _score_popularidad
--    score = log1p(clicks_24h), cap en 3
CREATE OR REPLACE VIEW eventos_popularidad_24h AS
SELECT
  item_id AS evento_id,
  COUNT(*) AS interacciones_24h,
  LN(1 + COUNT(*)) AS score_popularidad  -- log1p
FROM interacciones_usuario
WHERE created_at >= NOW() - INTERVAL '24 hours'
  AND tipo IN ('view_evento', 'click')
GROUP BY item_id;

-- 5. Índice en eventos.fuente_url para las consultas Poisson del scheduler
CREATE INDEX IF NOT EXISTS idx_eventos_fuente_url_created
  ON eventos (fuente_url, created_at DESC)
  WHERE fuente_url IS NOT NULL;

-- 6. Índice en eventos.espacio_id para _rank_lugares_by_poisson
CREATE INDEX IF NOT EXISTS idx_eventos_espacio_created
  ON eventos (espacio_id, created_at DESC)
  WHERE espacio_id IS NOT NULL;
