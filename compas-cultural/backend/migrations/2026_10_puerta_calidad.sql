-- ════════════════════════════════════════════════════════════════════════
-- 2026-10 · Puerta de calidad de eventos (app/services/event_gate.py)
-- Ejecutar en Supabase → SQL Editor. Idempotente.
-- ════════════════════════════════════════════════════════════════════════

-- Motivo por el que un evento quedó oculto: 'gate:rechazar:...', 'gate:cuarentena:...',
-- 'gate:duplicado:<id del que se conservó>'. Lo usa el Admin (/admin/cuarentena).
ALTER TABLE public.eventos ADD COLUMN IF NOT EXISTS oculto_motivo TEXT;
CREATE INDEX IF NOT EXISTS idx_eventos_oculto_motivo ON public.eventos (oculto_motivo) WHERE oculto = TRUE;

-- Para REVERTIR todo lo que ocultó la puerta (si hiciera falta):
--   UPDATE public.eventos SET oculto = FALSE, oculto_motivo = NULL WHERE oculto_motivo LIKE 'gate:%';
