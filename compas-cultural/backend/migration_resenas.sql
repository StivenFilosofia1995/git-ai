-- Migration: Reviews/Ratings System
-- Run this in Supabase SQL Editor

CREATE TABLE IF NOT EXISTS resenas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    user_nombre TEXT,
    tipo TEXT NOT NULL CHECK (tipo IN ('evento', 'espacio')),
    item_id UUID NOT NULL,
    puntuacion INTEGER NOT NULL CHECK (puntuacion >= 1 AND puntuacion <= 5),
    titulo TEXT,
    comentario TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_resenas_item ON resenas(tipo, item_id);
CREATE INDEX IF NOT EXISTS idx_resenas_user ON resenas(user_id);
CREATE INDEX IF NOT EXISTS idx_resenas_puntuacion ON resenas(puntuacion);

-- One review per user per item
CREATE UNIQUE INDEX IF NOT EXISTS idx_resenas_unique_user_item ON resenas(user_id, tipo, item_id);

-- RLS
ALTER TABLE resenas ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Resenas visible para todos" ON resenas
    FOR SELECT USING (true);

CREATE POLICY "Usuarios autenticados pueden crear resenas" ON resenas
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Usuarios pueden editar sus propias resenas" ON resenas
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Usuarios pueden borrar sus propias resenas" ON resenas
    FOR DELETE USING (auth.uid() = user_id);
