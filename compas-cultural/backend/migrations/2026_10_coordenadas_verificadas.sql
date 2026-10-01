-- ════════════════════════════════════════════════════════════════════════
-- 2026-10 · Coordenadas verificadas de lugares
-- Ejecutar en Supabase → SQL Editor DESPUÉS de 2026_10_datos_confiables.sql.
-- Idempotente.
-- ════════════════════════════════════════════════════════════════════════

-- Auditoría de cada coordenada (la usa app/services/geo_verificacion.py)
ALTER TABLE public.lugares ADD COLUMN IF NOT EXISTS coords_verificadas_en TIMESTAMPTZ;
ALTER TABLE public.lugares ADD COLUMN IF NOT EXISTS coords_estado TEXT;   -- ok | corregir | nuevo | placeholder | sin_verificar | manual
ALTER TABLE public.lugares ADD COLUMN IF NOT EXISTS coords_fuente TEXT;   -- osm:node/123 | manual | ...

CREATE INDEX IF NOT EXISTS idx_lugares_coords_verificadas_en ON public.lugares (coords_verificadas_en NULLS FIRST);
