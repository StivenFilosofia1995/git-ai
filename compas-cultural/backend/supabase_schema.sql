-- =====================================================
-- Compás Cultural — Schema para Supabase
-- Ejecutar en: Supabase Dashboard → SQL Editor → New Query
-- =====================================================

-- 1. Eliminar tablas vacías existentes (sin pérdida de datos)
DROP TABLE IF EXISTS eventos CASCADE;
DROP TABLE IF EXISTS lugares CASCADE;
DROP TABLE IF EXISTS memoria_consultas CASCADE;

-- 2. Tabla principal: LUGARES (espacios culturales)
CREATE TABLE lugares (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  nombre VARCHAR(255) NOT NULL,
  slug VARCHAR(255) UNIQUE NOT NULL,
  tipo VARCHAR(50) NOT NULL,                         -- espacio_fisico, colectivo, festival, etc.
  categorias TEXT[] DEFAULT '{}',
  categoria_principal VARCHAR(50) NOT NULL,            -- teatro, jazz, hip_hop, galeria, etc.
  municipio VARCHAR(50) DEFAULT 'medellin' NOT NULL,
  barrio VARCHAR(100),
  comuna VARCHAR(50),
  direccion VARCHAR(255),
  lat DOUBLE PRECISION,
  lng DOUBLE PRECISION,
  descripcion_corta VARCHAR(300),
  descripcion TEXT,
  enfoque_estrategico TEXT,
  contexto_historico TEXT,
  instagram_handle VARCHAR(100),
  instagram_seguidores INTEGER,
  sitio_web VARCHAR(500),
  telefono VARCHAR(50),
  email VARCHAR(255),
  facebook VARCHAR(255),
  nivel_actividad VARCHAR(30) DEFAULT 'activo' NOT NULL,  -- muy_activo, activo, moderado, emergente, historico, cerrado
  es_underground BOOLEAN DEFAULT FALSE,
  es_institucional BOOLEAN DEFAULT FALSE,
  modelo_sostenibilidad VARCHAR(100),
  año_fundacion INTEGER,
  fuente_datos VARCHAR(100) DEFAULT 'investigacion_base',
  ultima_verificacion TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- 3. Tabla: EVENTOS
CREATE TABLE eventos (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  titulo VARCHAR(500) NOT NULL,
  slug VARCHAR(500) UNIQUE NOT NULL,
  espacio_id UUID REFERENCES lugares(id) ON DELETE SET NULL,
  fecha_inicio TIMESTAMPTZ NOT NULL,
  fecha_fin TIMESTAMPTZ,
  es_recurrente BOOLEAN DEFAULT FALSE,
  patron_recurrencia JSONB,
  categorias TEXT[] DEFAULT '{}',
  categoria_principal VARCHAR(50) NOT NULL,
  municipio VARCHAR(50) DEFAULT 'medellin',
  barrio VARCHAR(100),
  direccion VARCHAR(255),
  lat DOUBLE PRECISION,
  lng DOUBLE PRECISION,
  nombre_lugar VARCHAR(255),
  descripcion TEXT,
  imagen_url VARCHAR(500),
  precio VARCHAR(100),
  es_gratuito BOOLEAN DEFAULT FALSE,
  fuente VARCHAR(50) NOT NULL,             -- instagram, sitio_web, scraping_llm, manual
  fuente_url VARCHAR(500),
  fuente_post_id VARCHAR(255),
  verificado BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- 4. Tabla: MEMORIA DE CONSULTAS IA
CREATE TABLE memoria_consultas (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  session_id TEXT,
  pregunta TEXT,
  respuesta TEXT,
  contexto JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 5. Tabla: ZONAS CULTURALES
CREATE TABLE zonas_culturales (
  id SERIAL PRIMARY KEY,
  nombre VARCHAR(100) NOT NULL,
  slug VARCHAR(100) UNIQUE NOT NULL,
  descripcion TEXT,
  vocacion VARCHAR(255),
  municipio VARCHAR(50) DEFAULT 'medellin'
);

-- 6. Tabla: ARTISTAS
CREATE TABLE artistas (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  nombre VARCHAR(255) NOT NULL,
  slug VARCHAR(255) UNIQUE NOT NULL,
  categorias TEXT[] DEFAULT '{}',
  bio TEXT,
  municipio VARCHAR(50),
  barrio VARCHAR(100),
  instagram_handle VARCHAR(100),
  sitio_web VARCHAR(500),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- 7. Tabla: SCRAPING LOG
CREATE TABLE scraping_log (
  id SERIAL PRIMARY KEY,
  fuente VARCHAR(50) NOT NULL,
  ejecutado_en TIMESTAMPTZ DEFAULT now(),
  registros_nuevos INTEGER DEFAULT 0,
  registros_actualizados INTEGER DEFAULT 0,
  errores INTEGER DEFAULT 0,
  detalle JSONB,
  duracion_segundos DOUBLE PRECISION
);

-- 8. Tabla: SOLICITUDES DE REGISTRO (URL scraping)
CREATE TABLE solicitudes_registro (
  id SERIAL PRIMARY KEY,
  url VARCHAR(1000) NOT NULL,
  tipo_url VARCHAR(50) NOT NULL,
  estado VARCHAR(30) DEFAULT 'pendiente' NOT NULL,
  datos_extraidos JSONB,
  espacio_id UUID,
  mensaje TEXT,
  ip_solicitante VARCHAR(45),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- 9. Tabla: PERFILES DE USUARIO
CREATE TABLE perfiles_usuario (
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

-- 10. Tabla: HISTORIAL DE BÚSQUEDA (para recomendaciones)
CREATE TABLE historial_busqueda (
  id SERIAL PRIMARY KEY,
  user_id UUID NOT NULL,
  query TEXT NOT NULL,
  categorias_resultado TEXT[] DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 11. Tabla: INTERACCIONES DE USUARIO
CREATE TABLE interacciones_usuario (
  id SERIAL PRIMARY KEY,
  user_id UUID NOT NULL,
  tipo VARCHAR(20) NOT NULL,
  item_id VARCHAR(255) NOT NULL,
  categoria VARCHAR(50),
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 12. Índices para rendimiento
CREATE INDEX idx_eventos_fecha ON eventos(fecha_inicio);
CREATE INDEX idx_eventos_municipio ON eventos(municipio);
CREATE INDEX idx_eventos_categoria ON eventos(categoria_principal);
CREATE INDEX idx_eventos_espacio_id ON eventos(espacio_id);
CREATE INDEX idx_eventos_municipio_cat_fecha ON eventos(municipio, categoria_principal, fecha_inicio DESC);
CREATE INDEX idx_lugares_municipio ON lugares(municipio);
CREATE INDEX idx_lugares_slug ON lugares(slug);
CREATE INDEX idx_eventos_slug ON eventos(slug);
CREATE INDEX idx_lugares_actividad ON lugares(nivel_actividad);
CREATE INDEX idx_perfiles_user_id ON perfiles_usuario(user_id);
CREATE INDEX idx_historial_user_id ON historial_busqueda(user_id);
CREATE INDEX idx_historial_created ON historial_busqueda(created_at);
CREATE INDEX idx_historial_user_created ON historial_busqueda(user_id, created_at DESC);
CREATE INDEX idx_interacciones_user_id ON interacciones_usuario(user_id);
CREATE INDEX idx_interacciones_created ON interacciones_usuario(created_at);
CREATE INDEX idx_interacciones_user_tipo ON interacciones_usuario(user_id, tipo, created_at DESC);

-- 13. Row Level Security (RLS)
-- Tablas de usuario: solo el dueño puede ver/editar sus datos
ALTER TABLE perfiles_usuario ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view own profile" ON perfiles_usuario FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own profile" ON perfiles_usuario FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own profile" ON perfiles_usuario FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Service role full access on perfiles" ON perfiles_usuario FOR ALL USING (auth.role() = 'service_role');

ALTER TABLE historial_busqueda ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view own search history" ON historial_busqueda FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own search history" ON historial_busqueda FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Service role full access on historial" ON historial_busqueda FOR ALL USING (auth.role() = 'service_role');

ALTER TABLE interacciones_usuario ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view own interactions" ON interacciones_usuario FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own interactions" ON interacciones_usuario FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Service role full access on interacciones" ON interacciones_usuario FOR ALL USING (auth.role() = 'service_role');

-- Tablas públicas: lectura abierta, escritura solo service_role
ALTER TABLE lugares ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read access on lugares" ON lugares FOR SELECT USING (true);
CREATE POLICY "Service role full access on lugares" ON lugares FOR ALL USING (auth.role() = 'service_role');

ALTER TABLE eventos ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read access on eventos" ON eventos FOR SELECT USING (true);
CREATE POLICY "Service role full access on eventos" ON eventos FOR ALL USING (auth.role() = 'service_role');

ALTER TABLE zonas_culturales ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read access on zonas" ON zonas_culturales FOR SELECT USING (true);
CREATE POLICY "Service role full access on zonas" ON zonas_culturales FOR ALL USING (auth.role() = 'service_role');

ALTER TABLE memoria_consultas ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access on memoria" ON memoria_consultas FOR ALL USING (auth.role() = 'service_role');

ALTER TABLE scraping_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access on scraping_log" ON scraping_log FOR ALL USING (auth.role() = 'service_role');

ALTER TABLE solicitudes_registro ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access on solicitudes" ON solicitudes_registro FOR ALL USING (auth.role() = 'service_role');
