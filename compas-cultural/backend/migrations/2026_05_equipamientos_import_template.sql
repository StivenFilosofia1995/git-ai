-- ============================================================
-- Import completo desde MARKDOWN (SBPM + UVAs + Teatros)
-- Requiere migracion: 2026_05_equipamientos_zonas_ml.sql
-- ============================================================

-- 1) Pegue TODO el contenido del .md dentro del bloque $md$ ... $md$
-- 2) Ejecute. El parser toma las tablas principales de los 3 grupos
--    y tambien la tabla de "Espacios analogos vigentes 2026".

WITH src AS (
  SELECT $md$
PASTE_AQUI_TODO_EL_MARKDOWN_COMPLETO
$md$::text AS md
)
SELECT importar_equipamientos_2026_desde_markdown(md) AS resumen
FROM src;

-- Validaciones sugeridas
SELECT
  grupo,
  count(*) AS total,
  count(*) FILTER (WHERE estado_operativo IN ('vigente', 'reapertura')) AS activos
FROM equipamientos_culturales_2026
GROUP BY grupo
ORDER BY grupo;

SELECT *
FROM oferta_cultural_por_zona_2026
ORDER BY equipamientos_activos DESC, equipamientos_total DESC
LIMIT 50;
