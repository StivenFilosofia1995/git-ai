-- =====================================================
-- Migration: RLS Policies + Performance Indexes
-- Ejecutar en: Supabase Dashboard → SQL Editor → New Query
-- =====================================================

-- ═══════════════════════════════════════════════════════
-- 1. ROW LEVEL SECURITY (RLS) — Proteger datos de usuario
-- ═══════════════════════════════════════════════════════

-- Perfiles de usuario: solo el dueño puede ver/editar su perfil
ALTER TABLE perfiles_usuario ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own profile"
  ON perfiles_usuario FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own profile"
  ON perfiles_usuario FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own profile"
  ON perfiles_usuario FOR UPDATE
  USING (auth.uid() = user_id);

-- Service role bypass (para el backend con service_role key)
CREATE POLICY "Service role full access on perfiles"
  ON perfiles_usuario FOR ALL
  USING (auth.role() = 'service_role');

-- Historial de búsqueda: solo el dueño puede ver su historial
ALTER TABLE historial_busqueda ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own search history"
  ON historial_busqueda FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own search history"
  ON historial_busqueda FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Service role full access on historial"
  ON historial_busqueda FOR ALL
  USING (auth.role() = 'service_role');

-- Interacciones de usuario: solo el dueño puede ver sus interacciones
ALTER TABLE interacciones_usuario ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own interactions"
  ON interacciones_usuario FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own interactions"
  ON interacciones_usuario FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Service role full access on interacciones"
  ON interacciones_usuario FOR ALL
  USING (auth.role() = 'service_role');

-- Tablas públicas (lectura abierta): lugares, eventos, zonas_culturales
ALTER TABLE lugares ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read access on lugares"
  ON lugares FOR SELECT USING (true);
CREATE POLICY "Service role full access on lugares"
  ON lugares FOR ALL USING (auth.role() = 'service_role');

ALTER TABLE eventos ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read access on eventos"
  ON eventos FOR SELECT USING (true);
CREATE POLICY "Service role full access on eventos"
  ON eventos FOR ALL USING (auth.role() = 'service_role');

ALTER TABLE zonas_culturales ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read access on zonas"
  ON zonas_culturales FOR SELECT USING (true);
CREATE POLICY "Service role full access on zonas"
  ON zonas_culturales FOR ALL USING (auth.role() = 'service_role');

ALTER TABLE memoria_consultas ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access on memoria"
  ON memoria_consultas FOR ALL USING (auth.role() = 'service_role');

ALTER TABLE scraping_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access on scraping_log"
  ON scraping_log FOR ALL USING (auth.role() = 'service_role');

ALTER TABLE solicitudes_registro ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access on solicitudes"
  ON solicitudes_registro FOR ALL USING (auth.role() = 'service_role');

-- ═══════════════════════════════════════════════════════
-- 2. PERFORMANCE INDEXES
-- ═══════════════════════════════════════════════════════

-- Composite index for the most common query pattern: municipio + categoria + fecha
CREATE INDEX IF NOT EXISTS idx_eventos_municipio_cat_fecha
  ON eventos(municipio, categoria_principal, fecha_inicio DESC);

-- Foreign key index for JOINs
CREATE INDEX IF NOT EXISTS idx_eventos_espacio_id
  ON eventos(espacio_id);

-- Composite for user history queries
CREATE INDEX IF NOT EXISTS idx_historial_user_created
  ON historial_busqueda(user_id, created_at DESC);

-- Composite for user interaction queries
CREATE INDEX IF NOT EXISTS idx_interacciones_user_tipo
  ON interacciones_usuario(user_id, tipo, created_at DESC);
