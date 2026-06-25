-- Migración: Agregar campos faltantes a eventos para horas exactas, aforo y sesiones
-- Fecha: 2026-04-23
-- Propósito: Permitir que cada evento tenga hora exacta, aforo, sesión y mejor información de imagen

-- 1. Agregar columnas faltantes a eventos
ALTER TABLE eventos
ADD COLUMN IF NOT EXISTS hora_inicio TIME,           -- Hora exacta del evento (HH:MM)
ADD COLUMN IF NOT EXISTS hora_fin TIME,              -- Hora de fin (si aplica)
ADD COLUMN IF NOT EXISTS aforo INTEGER,              -- Capacidad del evento
ADD COLUMN IF NOT EXISTS sesion_numero INTEGER,      -- Número de sesión (ej: sesión 1, 2, etc.)
ADD COLUMN IF NOT EXISTS imagen_url_principal VARCHAR(500),  -- URL de imagen principal/portada
ADD COLUMN IF NOT EXISTS imagen_url_alternativa VARCHAR(500), -- URL de imagen alternativa
ADD COLUMN IF NOT EXISTS es_evento_registrado BOOLEAN DEFAULT FALSE;  -- TRUE si lo registró un usuario

-- 2. Crear índices para búsqueda más rápida
CREATE INDEX IF NOT EXISTS idx_eventos_hora_inicio ON eventos(hora_inicio);
CREATE INDEX IF NOT EXISTS idx_eventos_sesion ON eventos(sesion_numero);
CREATE INDEX IF NOT EXISTS idx_eventos_registrado ON eventos(es_evento_registrado);

-- 3. Agregar columnas para tracking de calidad de datos
ALTER TABLE eventos
ADD COLUMN IF NOT EXISTS tiene_hora_confirmada BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS tiene_imagen_confirmada BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS tiene_aforo_confirmado BOOLEAN DEFAULT FALSE;

-- 4. Crear tabla para almacenar múltiples imágenes de un evento
CREATE TABLE IF NOT EXISTS evento_imagenes (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  evento_id UUID NOT NULL REFERENCES eventos(id) ON DELETE CASCADE,
  imagen_url VARCHAR(500) NOT NULL,
  tipo VARCHAR(50),                  -- portada, galeria, flyer, ecard, etc.
  es_principal BOOLEAN DEFAULT FALSE,
  subida_por_usuario BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_evento_imagenes_evento ON evento_imagenes(evento_id);
CREATE INDEX IF NOT EXISTS idx_evento_imagenes_principal ON evento_imagenes(es_principal);

-- 5. Crear tabla para sesiones/aforos de eventos
CREATE TABLE IF NOT EXISTS evento_sesiones (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  evento_id UUID NOT NULL REFERENCES eventos(id) ON DELETE CASCADE,
  numero_sesion INTEGER NOT NULL,
  hora_inicio TIME,
  hora_fin TIME,
  aforo INTEGER,
  lugares_disponibles INTEGER,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_evento_sesiones_evento ON evento_sesiones(evento_id);
CREATE INDEX IF NOT EXISTS idx_evento_sesiones_numero ON evento_sesiones(numero_sesion);

-- 6. Comentarios útiles en la tabla
COMMENT ON COLUMN eventos.hora_inicio IS 'Hora exacta de inicio del evento en formato HH:MM (ej: 19:30)';
COMMENT ON COLUMN eventos.hora_fin IS 'Hora de fin del evento (opcional)';
COMMENT ON COLUMN eventos.aforo IS 'Capacidad/aforo del evento (cantidad de personas)';
COMMENT ON COLUMN eventos.sesion_numero IS 'Número de sesión si el evento tiene múltiples sesiones';
COMMENT ON COLUMN eventos.es_evento_registrado IS 'TRUE si fue registrado manualmente por usuario, FALSE si viene de scraping';
COMMENT ON COLUMN eventos.tiene_hora_confirmada IS 'TRUE si la hora fue confirmada por usuario o verificada';
COMMENT ON COLUMN eventos.tiene_imagen_confirmada IS 'TRUE si la imagen fue verificada como correcta';
