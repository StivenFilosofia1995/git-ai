-- Migration: Admin event upload + ML training feedback
-- Run once in Supabase SQL editor

-- 1. Oculto flag: admin can hide events from public API
ALTER TABLE eventos ADD COLUMN IF NOT EXISTS oculto BOOLEAN DEFAULT FALSE;

-- 2. Duration in minutes: for events with known duration
ALTER TABLE eventos ADD COLUMN IF NOT EXISTS duracion_minutos INTEGER;

-- 3. Partial index for fast oculto filter (only indexes hidden rows)
CREATE INDEX IF NOT EXISTS idx_eventos_oculto ON eventos(oculto) WHERE oculto = TRUE;

-- 4. ML training feedback: admin can label ambiguous events for continuous learning
CREATE TABLE IF NOT EXISTS ml_training_feedback (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    titulo      TEXT         NOT NULL,
    descripcion TEXT,
    fuente_url  TEXT,
    label       BOOLEAN      NOT NULL,  -- true = es evento cultural, false = no es evento
    created_at  TIMESTAMPTZ  DEFAULT now()
);
