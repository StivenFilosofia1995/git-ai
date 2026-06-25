-- ─────────────────────────────────────────────────────────────────────────────
-- Migración: vistas de eventos + feed algorítmico (2026-05)
-- Ejecutar en Supabase SQL Editor o via psql
-- ─────────────────────────────────────────────────────────────────────────────

-- ── 1. Tabla de vistas de eventos ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS evento_vistas (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    evento_id   UUID         NOT NULL REFERENCES eventos(id) ON DELETE CASCADE,
    user_id     UUID         REFERENCES auth.users(id) ON DELETE SET NULL,
    ip_hash     TEXT,           -- hashed IP para usuarios anónimos (privacidad)
    session_id  TEXT,           -- ID de sesión del navegador (deduplicación)
    viewed_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Índices para queries rápidas de conteo
CREATE INDEX IF NOT EXISTS idx_evento_vistas_evento_id  ON evento_vistas(evento_id);
CREATE INDEX IF NOT EXISTS idx_evento_vistas_user_id    ON evento_vistas(user_id);
CREATE INDEX IF NOT EXISTS idx_evento_vistas_viewed_at  ON evento_vistas(viewed_at DESC);
CREATE INDEX IF NOT EXISTS idx_evento_vistas_session    ON evento_vistas(session_id) WHERE session_id IS NOT NULL;

-- Índice compuesto para deduplicación por sesión
CREATE UNIQUE INDEX IF NOT EXISTS idx_evento_vistas_session_dedup
    ON evento_vistas(evento_id, session_id)
    WHERE session_id IS NOT NULL;

-- ── 2. Contador desnormalizado en eventos (para ORDER BY rápido) ─────────────
ALTER TABLE eventos ADD COLUMN IF NOT EXISTS vista_count  INTEGER NOT NULL DEFAULT 0;
ALTER TABLE eventos ADD COLUMN IF NOT EXISTS vistas_24h   INTEGER NOT NULL DEFAULT 0;

-- Índice para feed algorítmico
CREATE INDEX IF NOT EXISTS idx_eventos_vista_count ON eventos(vista_count DESC);
CREATE INDEX IF NOT EXISTS idx_eventos_vistas_24h  ON eventos(vistas_24h DESC);

-- ── 3. Función RPC para incrementar contador (llamada desde backend) ─────────
CREATE OR REPLACE FUNCTION increment_vista_count(p_evento_id UUID)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    UPDATE eventos
    SET
        vista_count = vista_count + 1,
        vistas_24h  = (
            SELECT COUNT(*) FROM evento_vistas
            WHERE evento_id = p_evento_id
              AND viewed_at > now() - INTERVAL '24 hours'
        )
    WHERE id = p_evento_id;
END;
$$;

-- ── 4. Función RPC para refresh masivo de contadores (job nocturno) ──────────
CREATE OR REPLACE FUNCTION refresh_all_vista_counts()
RETURNS void
LANGUAGE sql
SECURITY DEFINER
AS $$
    UPDATE eventos e
    SET
        vista_count = (
            SELECT COUNT(*) FROM evento_vistas WHERE evento_id = e.id
        ),
        vistas_24h = (
            SELECT COUNT(*) FROM evento_vistas
            WHERE evento_id = e.id
              AND viewed_at > now() - INTERVAL '24 hours'
        );
$$;

-- ── 5. Tabla de perfiles de usuario (si no existe) ───────────────────────────
-- Complementa Supabase Auth con datos de perfil cultural
CREATE TABLE IF NOT EXISTS perfiles (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID         NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    nombre           TEXT         NOT NULL DEFAULT '',
    apellido         TEXT         NOT NULL DEFAULT '',
    email            TEXT         NOT NULL,
    telefono         TEXT,
    bio              TEXT,
    preferencias     TEXT[]       NOT NULL DEFAULT '{}',
    zona_id          INTEGER,
    municipio        TEXT         NOT NULL DEFAULT 'medellin',
    ubicacion_barrio TEXT,
    ubicacion_lat    DOUBLE PRECISION,
    ubicacion_lng    DOUBLE PRECISION,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_perfiles_user_id ON perfiles(user_id);

-- Trigger para updated_at automático
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'trg_perfiles_updated_at'
    ) THEN
        CREATE TRIGGER trg_perfiles_updated_at
            BEFORE UPDATE ON perfiles
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;

-- ── 6. RLS (Row Level Security) para perfiles ────────────────────────────────
ALTER TABLE perfiles ENABLE ROW LEVEL SECURITY;

-- Usuarios ven su propio perfil
CREATE POLICY IF NOT EXISTS "perfil_select_own"
    ON perfiles FOR SELECT
    USING (auth.uid() = user_id);

-- Usuarios actualizan su propio perfil
CREATE POLICY IF NOT EXISTS "perfil_update_own"
    ON perfiles FOR UPDATE
    USING (auth.uid() = user_id);

-- Service role puede hacer todo (para el backend)
CREATE POLICY IF NOT EXISTS "perfil_service_role_all"
    ON perfiles FOR ALL
    USING (auth.role() = 'service_role');

-- ── 7. RLS para evento_vistas ────────────────────────────────────────────────
ALTER TABLE evento_vistas ENABLE ROW LEVEL SECURITY;

-- Cualquiera puede insertar vistas (anónimo o autenticado)
CREATE POLICY IF NOT EXISTS "vistas_insert_all"
    ON evento_vistas FOR INSERT
    WITH CHECK (true);

-- Solo service role puede leer todas las vistas
CREATE POLICY IF NOT EXISTS "vistas_select_service"
    ON evento_vistas FOR SELECT
    USING (auth.role() = 'service_role');

-- ── 8. Vista materializada para trending (opcional, rendimiento) ─────────────
-- Se puede usar para el feed algorítmico de alta carga
CREATE OR REPLACE VIEW eventos_trending AS
SELECT
    e.id,
    e.titulo,
    e.categoria_principal,
    e.fecha_inicio,
    e.municipio,
    e.imagen_url,
    e.es_gratuito,
    COALESCE(v24.cnt, 0)  AS vistas_24h,
    COALESCE(v7d.cnt, 0)  AS vistas_7d,
    COALESCE(v_all.cnt, 0) AS vistas_total
FROM eventos e
LEFT JOIN (
    SELECT evento_id, COUNT(*) AS cnt
    FROM evento_vistas
    WHERE viewed_at > now() - INTERVAL '24 hours'
    GROUP BY evento_id
) v24 ON v24.evento_id = e.id
LEFT JOIN (
    SELECT evento_id, COUNT(*) AS cnt
    FROM evento_vistas
    WHERE viewed_at > now() - INTERVAL '7 days'
    GROUP BY evento_id
) v7d ON v7d.evento_id = e.id
LEFT JOIN (
    SELECT evento_id, COUNT(*) AS cnt
    FROM evento_vistas
    GROUP BY evento_id
) v_all ON v_all.evento_id = e.id
WHERE e.fecha_inicio >= now();
