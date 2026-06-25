-- =====================================================
-- Cultura ETÉREA — Migración: tablas faltantes
-- Ejecutar en: Supabase Dashboard → SQL Editor → New Query → Run
-- Solo crea lo que falta. NO toca tablas existentes con datos.
-- =====================================================

-- ==========================================
-- 1. TABLA: PERFILES DE USUARIO (NUEVA)
-- ==========================================
CREATE TABLE IF NOT EXISTS perfiles_usuario (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID UNIQUE NOT NULL,
  nombre VARCHAR(100) NOT NULL,
  apellido VARCHAR(100) NOT NULL,
  email VARCHAR(255) NOT NULL,
  telefono VARCHAR(50),
  bio TEXT,
  preferencias TEXT[] DEFAULT '{}',
  zona_id INTEGER REFERENCES zonas_culturales(id) ON DELETE SET NULL,
  municipio VARCHAR(50) DEFAULT 'medellin',
  ubicacion_barrio VARCHAR(100),
  ubicacion_lat DOUBLE PRECISION,
  ubicacion_lng DOUBLE PRECISION,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- ==========================================
-- 2. TABLA: HISTORIAL DE BÚSQUEDA (NUEVA)
-- ==========================================
CREATE TABLE IF NOT EXISTS historial_busqueda (
  id SERIAL PRIMARY KEY,
  user_id UUID NOT NULL,
  query TEXT NOT NULL,
  categorias_resultado TEXT[] DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now()
);

-- ==========================================
-- 3. TABLA: INTERACCIONES DE USUARIO (NUEVA)
-- ==========================================
CREATE TABLE IF NOT EXISTS interacciones_usuario (
  id SERIAL PRIMARY KEY,
  user_id UUID NOT NULL,
  tipo VARCHAR(20) NOT NULL,
  item_id VARCHAR(255) NOT NULL,
  categoria VARCHAR(50),
  created_at TIMESTAMPTZ DEFAULT now()
);

-- ==========================================
-- 4. ÍNDICES
-- ==========================================
CREATE INDEX IF NOT EXISTS idx_perfiles_user_id ON perfiles_usuario(user_id);
CREATE INDEX IF NOT EXISTS idx_historial_user_id ON historial_busqueda(user_id);
CREATE INDEX IF NOT EXISTS idx_historial_created ON historial_busqueda(created_at);
CREATE INDEX IF NOT EXISTS idx_interacciones_user_id ON interacciones_usuario(user_id);
CREATE INDEX IF NOT EXISTS idx_interacciones_created ON interacciones_usuario(created_at);

-- ==========================================
-- 5. ROW LEVEL SECURITY (RLS)
-- ==========================================
ALTER TABLE perfiles_usuario ENABLE ROW LEVEL SECURITY;
ALTER TABLE historial_busqueda ENABLE ROW LEVEL SECURITY;
ALTER TABLE interacciones_usuario ENABLE ROW LEVEL SECURITY;

-- Política: service_role puede todo (es la key del backend)
CREATE POLICY "service_role_all_perfiles" ON perfiles_usuario
  FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_role_all_historial" ON historial_busqueda
  FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_role_all_interacciones" ON interacciones_usuario
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Política: usuarios autenticados pueden ver/editar sus propios datos
CREATE POLICY "users_own_perfil" ON perfiles_usuario
  FOR ALL TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "users_own_historial" ON historial_busqueda
  FOR ALL TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "users_own_interacciones" ON interacciones_usuario
  FOR ALL TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- ==========================================
-- 6. COLUMNAS FALTANTES EN TABLAS EXISTENTES
-- ==========================================
-- Agregar imagen_url a lugares (si no existe)
ALTER TABLE lugares ADD COLUMN IF NOT EXISTS imagen_url VARCHAR(500);

-- ==========================================
-- VERIFICACIÓN
-- ==========================================
DO $$
DECLARE
  t TEXT;
  tables TEXT[] := ARRAY['lugares','eventos','memoria_consultas','zonas_culturales','artistas','scraping_log','solicitudes_registro','perfiles_usuario','historial_busqueda','interacciones_usuario'];
BEGIN
  FOREACH t IN ARRAY tables LOOP
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = t) THEN
      RAISE NOTICE '✓ %', t;
    ELSE
      RAISE WARNING '✗ FALTA: %', t;
    END IF;
  END LOOP;
  RAISE NOTICE '— Migración completada —';
END $$;
