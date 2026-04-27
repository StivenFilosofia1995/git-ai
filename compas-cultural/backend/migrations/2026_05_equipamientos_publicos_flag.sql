-- ============================================================
-- Columna es_equipamiento_publico en tabla lugares
-- Marca bibliotecas públicas (SBPM/BPP), UVAs y teatros oficiales
-- para que el mapa y el scraper los trate de forma diferenciada
-- ============================================================

ALTER TABLE lugares
  ADD COLUMN IF NOT EXISTS es_equipamiento_publico BOOLEAN NOT NULL DEFAULT FALSE;

-- Índice parcial para filtrar rápidamente
CREATE INDEX IF NOT EXISTS idx_lugares_equipamiento_publico
  ON lugares (es_equipamiento_publico)
  WHERE es_equipamiento_publico = TRUE;

-- Vista útil para admin: equipamientos públicos con sus stats
CREATE OR REPLACE VIEW equipamientos_culturales_publicos AS
SELECT
  l.id,
  l.nombre,
  l.slug,
  l.tipo,
  l.categoria_principal,
  l.municipio,
  l.barrio,
  l.sitio_web,
  l.instagram_handle,
  l.nivel_actividad,
  COUNT(e.id) FILTER (WHERE e.fecha_inicio >= CURRENT_DATE) AS eventos_proximos
FROM lugares l
LEFT JOIN eventos e ON e.nombre_lugar ILIKE '%' || l.nombre || '%'
  OR e.lugar_id = l.id
WHERE l.es_equipamiento_publico = TRUE
GROUP BY l.id
ORDER BY eventos_proximos DESC, l.nombre;
