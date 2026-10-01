-- ════════════════════════════════════════════════════════════════════════
-- 2026-10 · Datos confiables (Fase 1 del rediseño)
-- Ejecutar en Supabase → SQL Editor. Es idempotente: se puede correr varias veces.
-- ════════════════════════════════════════════════════════════════════════

-- 1) Asegurar que el trigger que borraba las horas NO exista.
--    (migrations/2026_05_disable_event_hours.sql lo creaba; en producción no
--    estaba aplicado, pero si alguien lo corre de nuevo, las horas se pierden.)
DROP TRIGGER IF EXISTS trg_eventos_force_no_hour ON public.eventos;
DROP FUNCTION IF EXISTS public.eventos_force_no_hour();

-- 2) fecha_fin absurda (año 2076 de Compás Urbano, o anterior al inicio) → NULL
UPDATE public.eventos
SET fecha_fin = NULL
WHERE fecha_fin IS NOT NULL
  AND (fecha_fin > now() + interval '2 years' OR fecha_fin < fecha_inicio);

-- 3) Heredar coordenadas / barrio / municipio del lugar cuando el evento no las tiene
UPDATE public.eventos e
SET lat = l.lat,
    lng = l.lng
FROM public.lugares l
WHERE e.espacio_id = l.id
  AND e.lat IS NULL
  AND l.lat IS NOT NULL
  AND l.lng IS NOT NULL;

UPDATE public.eventos e
SET barrio = COALESCE(e.barrio, l.barrio),
    municipio = COALESCE(e.municipio, l.municipio),
    nombre_lugar = COALESCE(e.nombre_lugar, l.nombre)
FROM public.lugares l
WHERE e.espacio_id = l.id
  AND (e.barrio IS NULL OR e.municipio IS NULL OR e.nombre_lugar IS NULL);

-- 4) Trigger: todo evento nuevo hereda las coordenadas de su lugar
CREATE OR REPLACE FUNCTION public.eventos_heredar_lugar()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  l RECORD;
BEGIN
  IF NEW.espacio_id IS NOT NULL AND (NEW.lat IS NULL OR NEW.barrio IS NULL OR NEW.municipio IS NULL) THEN
    SELECT lat, lng, barrio, municipio, nombre INTO l FROM public.lugares WHERE id = NEW.espacio_id;
    IF FOUND THEN
      IF NEW.lat IS NULL AND l.lat IS NOT NULL AND l.lng IS NOT NULL THEN
        NEW.lat := l.lat;
        NEW.lng := l.lng;
      END IF;
      NEW.barrio := COALESCE(NEW.barrio, l.barrio);
      NEW.municipio := COALESCE(NEW.municipio, l.municipio);
      NEW.nombre_lugar := COALESCE(NEW.nombre_lugar, l.nombre);
    END IF;
  END IF;
  IF NEW.fecha_fin IS NOT NULL AND (NEW.fecha_fin > now() + interval '2 years' OR NEW.fecha_fin < NEW.fecha_inicio) THEN
    NEW.fecha_fin := NULL;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_eventos_heredar_lugar ON public.eventos;
CREATE TRIGGER trg_eventos_heredar_lugar
BEFORE INSERT OR UPDATE OF espacio_id, lat, fecha_fin ON public.eventos
FOR EACH ROW
EXECUTE FUNCTION public.eventos_heredar_lugar();

-- 5) Columna de moderación (el frontend filtra por ella; si falta, Supabase responde 400)
ALTER TABLE public.eventos ADD COLUMN IF NOT EXISTS estado_moderacion TEXT DEFAULT 'aprobado';
ALTER TABLE public.eventos ADD COLUMN IF NOT EXISTS oculto BOOLEAN DEFAULT FALSE;

-- Verificación rápida
SELECT
  count(*) FILTER (WHERE lat IS NOT NULL)            AS con_coordenadas,
  count(*) FILTER (WHERE hora_confirmada)            AS con_hora,
  count(*) FILTER (WHERE fecha_fin > now() + interval '2 years') AS fechas_absurdas,
  count(*)                                           AS total
FROM public.eventos;
