-- OCR + media evidence pipeline for event date/time quality
-- Run in Supabase SQL editor.

BEGIN;

-- 1) Stores event-related media evidence (flyer URL, card screenshot, page screenshot)
CREATE TABLE IF NOT EXISTS public.event_media_assets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  evento_id UUID NULL REFERENCES public.eventos(id) ON DELETE SET NULL,
  fuente TEXT NULL,
  fuente_url TEXT NULL,
  media_type TEXT NOT NULL CHECK (media_type IN ('flyer','ecard_screenshot','webpage_screenshot','og_image','other')),
  media_url TEXT NOT NULL,
  checksum_sha256 TEXT NULL,
  width_px INTEGER NULL,
  height_px INTEGER NULL,
  mime_type TEXT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_event_media_assets_evento_id ON public.event_media_assets(evento_id);
CREATE INDEX IF NOT EXISTS idx_event_media_assets_media_type ON public.event_media_assets(media_type);
CREATE INDEX IF NOT EXISTS idx_event_media_assets_fuente_url ON public.event_media_assets(fuente_url);

-- 2) Stores OCR runs and extracted fields for traceability + reprocessing
CREATE TABLE IF NOT EXISTS public.event_ocr_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  evento_id UUID NULL REFERENCES public.eventos(id) ON DELETE SET NULL,
  media_asset_id UUID NULL REFERENCES public.event_media_assets(id) ON DELETE SET NULL,
  image_url TEXT NOT NULL,
  backend TEXT NOT NULL DEFAULT 'easyocr',
  status TEXT NOT NULL DEFAULT 'ok' CHECK (status IN ('ok','error','empty')),
  raw_text TEXT NULL,
  extracted_date_text TEXT NULL,
  extracted_time_text TEXT NULL,
  extracted_hour INTEGER NULL,
  extracted_minute INTEGER NULL,
  confidence_time NUMERIC(5,4) NULL,
  confidence_date NUMERIC(5,4) NULL,
  timezone TEXT NOT NULL DEFAULT 'America/Bogota',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_event_ocr_runs_evento_id ON public.event_ocr_runs(evento_id);
CREATE INDEX IF NOT EXISTS idx_event_ocr_runs_media_asset_id ON public.event_ocr_runs(media_asset_id);
CREATE INDEX IF NOT EXISTS idx_event_ocr_runs_image_url ON public.event_ocr_runs(image_url);
CREATE INDEX IF NOT EXISTS idx_event_ocr_runs_created_at ON public.event_ocr_runs(created_at DESC);

-- Optional: keeps normalized quality metadata directly on eventos table.
ALTER TABLE public.eventos
  ADD COLUMN IF NOT EXISTS fecha_texto_original TEXT NULL,
  ADD COLUMN IF NOT EXISTS hora_texto_original TEXT NULL,
  ADD COLUMN IF NOT EXISTS confianza_fecha NUMERIC(5,4) NULL,
  ADD COLUMN IF NOT EXISTS confianza_hora NUMERIC(5,4) NULL,
  ADD COLUMN IF NOT EXISTS media_asset_id UUID NULL REFERENCES public.event_media_assets(id) ON DELETE SET NULL;

COMMIT;
