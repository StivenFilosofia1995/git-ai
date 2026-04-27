-- Politica no-horas: no mostrar ni marcar horas confiables en eventos.

-- 1) Limpiar data histórica: flags y componentes de hora.
-- 2) Enforzar data futura con trigger BEFORE INSERT/UPDATE.

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'eventos'
      AND column_name = 'hora_confirmada'
  ) THEN
    EXECUTE 'ALTER TABLE eventos ALTER COLUMN hora_confirmada SET DEFAULT FALSE';
    EXECUTE 'UPDATE eventos SET hora_confirmada = FALSE WHERE hora_confirmada IS DISTINCT FROM FALSE';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'eventos'
      AND column_name = 'tiene_hora_confirmada'
  ) THEN
    EXECUTE 'ALTER TABLE eventos ALTER COLUMN tiene_hora_confirmada SET DEFAULT FALSE';
    EXECUTE 'UPDATE eventos SET tiene_hora_confirmada = FALSE WHERE tiene_hora_confirmada IS DISTINCT FROM FALSE';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'eventos'
      AND column_name = 'hora_inicio'
  ) THEN
    EXECUTE 'UPDATE eventos SET hora_inicio = NULL WHERE hora_inicio IS NOT NULL';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'eventos'
      AND column_name = 'hora_fin'
  ) THEN
    EXECUTE 'UPDATE eventos SET hora_fin = NULL WHERE hora_fin IS NOT NULL';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'eventos'
      AND column_name = 'fecha_inicio'
  ) THEN
    EXECUTE 'UPDATE eventos SET fecha_inicio = date_trunc(''day'', fecha_inicio) WHERE fecha_inicio IS NOT NULL';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'eventos'
      AND column_name = 'fecha_fin'
  ) THEN
    EXECUTE 'UPDATE eventos SET fecha_fin = date_trunc(''day'', fecha_fin) WHERE fecha_fin IS NOT NULL';
  END IF;
END $$;

CREATE OR REPLACE FUNCTION public.eventos_force_no_hour()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.fecha_inicio := date_trunc('day', NEW.fecha_inicio);

  IF NEW.fecha_fin IS NOT NULL THEN
    NEW.fecha_fin := date_trunc('day', NEW.fecha_fin);
  END IF;

  NEW.hora_confirmada := FALSE;

  -- Algunos esquemas usan este flag alterno.
  BEGIN
    NEW.tiene_hora_confirmada := FALSE;
  EXCEPTION WHEN undefined_column THEN
    NULL;
  END;

  BEGIN
    NEW.hora_inicio := NULL;
  EXCEPTION WHEN undefined_column THEN
    NULL;
  END;

  BEGIN
    NEW.hora_fin := NULL;
  EXCEPTION WHEN undefined_column THEN
    NULL;
  END;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_eventos_force_no_hour ON public.eventos;

CREATE TRIGGER trg_eventos_force_no_hour
BEFORE INSERT OR UPDATE ON public.eventos
FOR EACH ROW
EXECUTE FUNCTION public.eventos_force_no_hour();
