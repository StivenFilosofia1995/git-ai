-- ============================================================
-- Migración: fix horas inventadas + scraping inteligente
-- Fecha: 2026-04-22
-- Safe to run multiple times (idempotente).
-- Aplicar en Supabase SQL Editor antes del deploy backend.
-- ============================================================

-- 1. Campo hora_confirmada en eventos
ALTER TABLE eventos
  ADD COLUMN IF NOT EXISTS hora_confirmada BOOLEAN DEFAULT FALSE;

-- 2. Campos de productividad en lugares
ALTER TABLE lugares
  ADD COLUMN IF NOT EXISTS runs_sin_eventos INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS ultimo_scrape_exitoso TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS ultimo_scrape_intento TIMESTAMPTZ;

-- 3. Índices de performance
CREATE INDEX IF NOT EXISTS idx_lugares_productividad
  ON lugares(nivel_actividad, runs_sin_eventos)
  WHERE nivel_actividad <> 'cerrado';

CREATE INDEX IF NOT EXISTS idx_eventos_fecha_inicio
  ON eventos(fecha_inicio);

CREATE INDEX IF NOT EXISTS idx_eventos_municipio_fecha
  ON eventos(municipio, fecha_inicio);

CREATE INDEX IF NOT EXISTS idx_eventos_categoria_principal
  ON eventos(categoria_principal);

-- 4. Marcar eventos legacy con hora sospechosa
-- Los eventos con hora exactamente 00:00:00 son "sin hora extraída"
UPDATE eventos
SET hora_confirmada = FALSE
WHERE EXTRACT(HOUR FROM fecha_inicio) = 0
  AND EXTRACT(MINUTE FROM fecha_inicio) = 0
  AND EXTRACT(SECOND FROM fecha_inicio) = 0;

-- 5. Eventos con hora 19:00:00 exacta Y fuente auto_scraper son sospechosos
-- (default histórico inventado). Los marcamos como no confiables
-- para que la UI los muestre como "Hora por confirmar" hasta el próximo scrape.
UPDATE eventos
SET hora_confirmada = FALSE
WHERE EXTRACT(HOUR FROM fecha_inicio) = 19
  AND EXTRACT(MINUTE FROM fecha_inicio) = 0
  AND EXTRACT(SECOND FROM fecha_inicio) = 0
  AND (
    fuente LIKE 'auto_scraper_%'
    OR fuente LIKE 'agenda_%'
    OR fuente = 'scraping'
  );

-- 6. Eventos con otra hora (no 00:00 ni 19:00-auto) → hora_confirmada = TRUE
UPDATE eventos
SET hora_confirmada = TRUE
WHERE (EXTRACT(HOUR FROM fecha_inicio) <> 0 OR EXTRACT(MINUTE FROM fecha_inicio) <> 0)
  AND NOT (
    EXTRACT(HOUR FROM fecha_inicio) = 19
    AND EXTRACT(MINUTE FROM fecha_inicio) = 0
    AND (fuente LIKE 'auto_scraper_%' OR fuente LIKE 'agenda_%' OR fuente = 'scraping')
  );

-- 7. Asegurar que ningún lugar quedó con nivel_actividad NULL
UPDATE lugares
SET nivel_actividad = 'activo'
WHERE nivel_actividad IS NULL;

-- 8. Reportes informativos
DO $$
DECLARE
  total_eventos INTEGER;
  con_hora INTEGER;
  sin_hora INTEGER;
  lugares_activos INTEGER;
BEGIN
  SELECT COUNT(*) INTO total_eventos FROM eventos;
  SELECT COUNT(*) INTO con_hora FROM eventos WHERE hora_confirmada = TRUE;
  SELECT COUNT(*) INTO sin_hora FROM eventos WHERE hora_confirmada = FALSE;
  SELECT COUNT(*) INTO lugares_activos FROM lugares WHERE nivel_actividad = 'activo';

  RAISE NOTICE '============================================';
  RAISE NOTICE 'Migración completada';
  RAISE NOTICE 'Eventos totales: %', total_eventos;
  RAISE NOTICE '  con hora confirmada: %', con_hora;
  RAISE NOTICE '  sin hora confirmada (se mostrarán como "Por confirmar"): %', sin_hora;
  RAISE NOTICE 'Lugares activos: %', lugares_activos;
  RAISE NOTICE '============================================';
END $$;
