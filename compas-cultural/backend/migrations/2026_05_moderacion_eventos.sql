-- ============================================================
-- Moderación de eventos publicados por usuarios
-- Agrega estado_moderacion a la tabla eventos
-- ============================================================

-- 1. Columna de moderación
ALTER TABLE eventos
  ADD COLUMN IF NOT EXISTS estado_moderacion TEXT
    NOT NULL DEFAULT 'aprobado'
    CHECK (estado_moderacion IN ('pendiente', 'aprobado', 'rechazado'));

-- 2. Los eventos publicados vía /publicar quedan pendientes
UPDATE eventos
SET estado_moderacion = 'pendiente'
WHERE fuente = 'usuario'
  AND verificado = FALSE
  AND estado_moderacion = 'aprobado';

-- 3. Índice para filtrar eventos aprobados/pendientes rápidamente
CREATE INDEX IF NOT EXISTS idx_eventos_moderacion
  ON eventos (estado_moderacion, fecha_inicio);

-- 4. Vista de moderación (para admin)
CREATE OR REPLACE VIEW eventos_pendientes_moderacion AS
SELECT
  e.id,
  e.titulo,
  e.fecha_inicio,
  e.municipio,
  e.barrio,
  e.fuente,
  e.estado_moderacion,
  e.created_at,
  l.nombre AS lugar_nombre
FROM eventos e
LEFT JOIN lugares l ON l.id = e.espacio_id
WHERE e.estado_moderacion = 'pendiente'
ORDER BY e.created_at DESC;
