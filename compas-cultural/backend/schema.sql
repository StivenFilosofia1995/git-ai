-- ============================================
-- SCHEMA SQL PARA COMPÁS CULTURAL
-- ============================================

-- Extensiones requeridas
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================
-- ENUMS
-- ============================================

CREATE TYPE categoria_cultural AS ENUM (
  'teatro',
  'hip_hop',
  'jazz',
  'musica_en_vivo',
  'electronica',
  'galeria',
  'arte_contemporaneo',
  'libreria',
  'editorial',
  'poesia',
  'filosofia',
  'cine',
  'danza',
  'circo',
  'fotografia',
  'casa_cultura',
  'centro_cultural',
  'festival',
  'batalla_freestyle',
  'muralismo',
  'radio_comunitaria',
  'publicacion',
  'otro'
);

CREATE TYPE nivel_actividad AS ENUM (
  'muy_activo',
  'activo',
  'moderado',
  'emergente',
  'historico',
  'cerrado'
);

CREATE TYPE tipo_entidad AS ENUM (
  'espacio_fisico',
  'colectivo',
  'festival',
  'editorial',
  'publicacion',
  'programa_institucional',
  'red_articuladora',
  'sello_discografico'
);

CREATE TYPE municipio_va AS ENUM (
  'medellin',
  'bello',
  'itagui',
  'envigado',
  'sabaneta',
  'caldas',
  'la_estrella',
  'copacabana',
  'girardota',
  'barbosa'
);

-- ============================================
-- TABLA: espacios_culturales
-- ============================================

CREATE TABLE espacios_culturales (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre VARCHAR(255) NOT NULL,
  slug VARCHAR(255) UNIQUE NOT NULL,
  tipo tipo_entidad NOT NULL,
  categorias categoria_cultural[] NOT NULL DEFAULT '{}',
  categoria_principal categoria_cultural NOT NULL,
  
  -- Ubicación
  municipio municipio_va NOT NULL DEFAULT 'medellin',
  barrio VARCHAR(100),
  comuna VARCHAR(50),
  direccion VARCHAR(255),
  coordenadas GEOGRAPHY(POINT, 4326),
  
  -- Descripción
  descripcion_corta VARCHAR(300),
  descripcion TEXT,
  enfoque_estrategico TEXT,
  contexto_historico TEXT,
  
  -- Contacto y redes
  instagram_handle VARCHAR(100),
  instagram_seguidores INTEGER,
  sitio_web VARCHAR(500),
  telefono VARCHAR(50),
  email VARCHAR(255),
  facebook VARCHAR(255),
  
  -- Metadatos
  nivel_actividad nivel_actividad NOT NULL DEFAULT 'activo',
  es_underground BOOLEAN DEFAULT FALSE,
  es_institucional BOOLEAN DEFAULT FALSE,
  modelo_sostenibilidad VARCHAR(100),
  año_fundacion INTEGER,
  
  -- Vectores para búsqueda semántica
  embedding vector(1536),
  
  -- Auditoría
  fuente_datos VARCHAR(100) DEFAULT 'investigacion_base',
  ultima_verificacion TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices
CREATE INDEX idx_espacios_categorias ON espacios_culturales USING GIN (categorias);
CREATE INDEX idx_espacios_municipio ON espacios_culturales (municipio);
CREATE INDEX idx_espacios_barrio ON espacios_culturales (barrio);
CREATE INDEX idx_espacios_geo ON espacios_culturales USING GIST (coordenadas);
CREATE INDEX idx_espacios_nombre_trgm ON espacios_culturales USING GIN (nombre gin_trgm_ops);
CREATE INDEX idx_espacios_embedding ON espacios_culturales USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);
CREATE INDEX idx_espacios_actividad ON espacios_culturales (nivel_actividad) WHERE nivel_actividad != 'cerrado';

-- ============================================
-- TABLA: eventos
-- ============================================

CREATE TABLE eventos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  titulo VARCHAR(500) NOT NULL,
  slug VARCHAR(500) UNIQUE NOT NULL,
  
  -- Relaciones
  espacio_id UUID REFERENCES espacios_culturales(id) ON DELETE SET NULL,
  
  -- Temporalidad
  fecha_inicio TIMESTAMPTZ NOT NULL,
  fecha_fin TIMESTAMPTZ,
  es_recurrente BOOLEAN DEFAULT FALSE,
  patron_recurrencia JSONB,
  
  -- Categorización
  categorias categoria_cultural[] NOT NULL DEFAULT '{}',
  categoria_principal categoria_cultural NOT NULL,
  
  -- Ubicación
  municipio municipio_va DEFAULT 'medellin',
  barrio VARCHAR(100),
  direccion VARCHAR(255),
  coordenadas GEOGRAPHY(POINT, 4326),
  nombre_lugar VARCHAR(255),
  
  -- Contenido
  descripcion TEXT,
  imagen_url VARCHAR(500),
  precio VARCHAR(100),
  es_gratuito BOOLEAN DEFAULT FALSE,
  
  -- Fuente
  fuente VARCHAR(50) NOT NULL,
  fuente_url VARCHAR(500),
  fuente_post_id VARCHAR(255),
  
  -- Vectores
  embedding vector(1536),
  
  -- Auditoría
  verificado BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices
CREATE INDEX idx_eventos_fecha ON eventos (fecha_inicio);
CREATE INDEX idx_eventos_espacio ON eventos (espacio_id);
CREATE INDEX idx_eventos_categorias ON eventos USING GIN (categorias);
CREATE INDEX idx_eventos_municipio ON eventos (municipio);
CREATE INDEX idx_eventos_barrio ON eventos (barrio);
CREATE INDEX idx_eventos_geo ON eventos USING GIST (coordenadas);
CREATE INDEX idx_eventos_fuente ON eventos (fuente);
CREATE INDEX idx_eventos_embedding ON eventos USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);

-- Vista materializada: eventos de hoy
CREATE MATERIALIZED VIEW eventos_hoy AS
SELECT e.*, ec.nombre AS nombre_espacio, ec.instagram_handle
FROM eventos e
LEFT JOIN espacios_culturales ec ON e.espacio_id = ec.id
WHERE e.fecha_inicio >= CURRENT_DATE
  AND e.fecha_inicio < CURRENT_DATE + INTERVAL '1 day'
ORDER BY e.fecha_inicio;

-- ============================================
-- TABLA: artistas
-- ============================================

CREATE TABLE artistas (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre VARCHAR(255) NOT NULL,
  slug VARCHAR(255) UNIQUE NOT NULL,
  categorias categoria_cultural[] DEFAULT '{}',
  bio TEXT,
  municipio municipio_va,
  barrio VARCHAR(100),
  instagram_handle VARCHAR(100),
  sitio_web VARCHAR(500),
  embedding vector(1536),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- TABLA: artistas_espacios (relación N:M)
-- ============================================

CREATE TABLE artistas_espacios (
  artista_id UUID REFERENCES artistas(id) ON DELETE CASCADE,
  espacio_id UUID REFERENCES espacios_culturales(id) ON DELETE CASCADE,
  rol VARCHAR(100),
  PRIMARY KEY (artista_id, espacio_id)
);

-- ============================================
-- TABLA: etiquetas
-- ============================================

CREATE TABLE etiquetas (
  id SERIAL PRIMARY KEY,
  nombre VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE espacios_etiquetas (
  espacio_id UUID REFERENCES espacios_culturales(id) ON DELETE CASCADE,
  etiqueta_id INTEGER REFERENCES etiquetas(id) ON DELETE CASCADE,
  PRIMARY KEY (espacio_id, etiqueta_id)
);

CREATE TABLE eventos_etiquetas (
  evento_id UUID REFERENCES eventos(id) ON DELETE CASCADE,
  etiqueta_id INTEGER REFERENCES etiquetas(id) ON DELETE CASCADE,
  PRIMARY KEY (evento_id, etiqueta_id)
);

-- ============================================
-- TABLA: scraping_log
-- ============================================

CREATE TABLE scraping_log (
  id SERIAL PRIMARY KEY,
  fuente VARCHAR(50) NOT NULL,
  ejecutado_en TIMESTAMPTZ DEFAULT NOW(),
  registros_nuevos INTEGER DEFAULT 0,
  registros_actualizados INTEGER DEFAULT 0,
  errores INTEGER DEFAULT 0,
  detalle JSONB,
  duracion_segundos FLOAT
);

-- ============================================
-- TABLA: zonas_culturales
-- ============================================

CREATE TABLE zonas_culturales (
  id SERIAL PRIMARY KEY,
  nombre VARCHAR(100) NOT NULL,
  slug VARCHAR(100) UNIQUE NOT NULL,
  descripcion TEXT,
  vocacion VARCHAR(255),
  poligono GEOGRAPHY(POLYGON, 4326),
  municipio municipio_va DEFAULT 'medellin'
);

-- Zonas iniciales
INSERT INTO zonas_culturales (nombre, slug, descripcion, vocacion, municipio) VALUES
('Distrito San Ignacio / Bomboná', 'san-ignacio-bombona', 'Mayor densidad cultural de la ciudad. Teatros, jazz, bohemia literaria.', 'teatral y contracultural', 'medellin'),
('Prado Centro', 'prado-centro', 'Único barrio patrimonial. Industrias creativas, casonas republicanas.', 'patrimonial e industrias creativas', 'medellin'),
('El Poblado - Manila - Provenza', 'poblado-manila-provenza', 'Galerismo internacional, jazz, vida nocturna cultural.', 'galerismo y mercado del arte', 'medellin'),
('Perpetuo Socorro', 'perpetuo-socorro', 'Distrito Creativo oficial. Bodegas convertidas en estudios.', 'distrito creativo y diseño', 'medellin'),
('Carlos E. Restrepo - Laureles - Estadio', 'carlos-e-laureles-estadio', 'Epicentro bohemio, librerías, academia, tertulias.', 'libresca y bohemia académica', 'medellin'),
('Ciudad del Río', 'ciudad-del-rio', 'MAMM, convergencia institucional y nocturna.', 'arte moderno y convergencia', 'medellin'),
('Comuna 13 - San Javier', 'comuna-13', 'Hip hop, graffiti, resistencia, Graffitour.', 'hip hop y resistencia urbana', 'medellin'),
('Aranjuez - Comuna 4', 'aranjuez-comuna-4', 'Crew Peligrosos, 4 Elementos Skuela, rap fusión.', 'hip hop y formación cultural', 'medellin'),
('Santa Cruz - Comuna 2', 'santa-cruz-comuna-2', 'Nuestra Gente, teatro comunitario.', 'teatro comunitario y títeres', 'medellin'),
('Manrique - Comuna 3', 'manrique-comuna-3', 'Hip hop, graffiti, narradores urbanos.', 'culturas urbanas', 'medellin');

-- ============================================
-- TABLA: solicitudes_registro
-- ============================================

CREATE TYPE estado_solicitud_registro AS ENUM ('pendiente', 'procesando', 'completado', 'error', 'rechazado');

CREATE TABLE solicitudes_registro (
  id SERIAL PRIMARY KEY,
  url VARCHAR(1000) NOT NULL,
  tipo_url VARCHAR(50) NOT NULL,
  estado estado_solicitud_registro DEFAULT 'pendiente' NOT NULL,
  datos_extraidos JSONB,
  espacio_id UUID REFERENCES espacios_culturales(id),
  mensaje TEXT,
  ip_solicitante VARCHAR(45),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_solicitudes_estado ON solicitudes_registro(estado);

-- ============================================
-- FUNCIONES
-- ============================================

-- Búsqueda geoespacial: eventos cerca de un punto
CREATE OR REPLACE FUNCTION eventos_cerca(
  lat DOUBLE PRECISION,
  lng DOUBLE PRECISION,
  radio_metros INTEGER DEFAULT 2000,
  limite INTEGER DEFAULT 20
)
RETURNS TABLE (
  id UUID,
  titulo VARCHAR,
  fecha_inicio TIMESTAMPTZ,
  categoria_principal categoria_cultural,
  barrio VARCHAR,
  distancia_metros DOUBLE PRECISION,
  nombre_espacio VARCHAR
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    e.id,
    e.titulo,
    e.fecha_inicio,
    e.categoria_principal,
    e.barrio,
    ST_Distance(
      e.coordenadas::geography,
      ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography
    ) AS distancia_metros,
    ec.nombre AS nombre_espacio
  FROM eventos e
  LEFT JOIN espacios_culturales ec ON e.espacio_id = ec.id
  WHERE ST_DWithin(
    e.coordenadas::geography,
    ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography,
    radio_metros
  )
  AND e.fecha_inicio >= NOW()
  ORDER BY e.fecha_inicio
  LIMIT limite;
END;
$$ LANGUAGE plpgsql;

-- Búsqueda semántica
CREATE OR REPLACE FUNCTION busqueda_semantica_espacios(
  query_embedding vector(1536),
  limite INTEGER DEFAULT 10,
  umbral FLOAT DEFAULT 0.7
)
RETURNS TABLE (
  id UUID,
  nombre VARCHAR,
  categoria_principal categoria_cultural,
  barrio VARCHAR,
  municipio municipio_va,
  similitud FLOAT
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    ec.id,
    ec.nombre,
    ec.categoria_principal,
    ec.barrio,
    ec.municipio,
    1 - (ec.embedding <=> query_embedding) AS similitud
  FROM espacios_culturales ec
  WHERE ec.embedding IS NOT NULL
    AND ec.nivel_actividad != 'cerrado'
    AND 1 - (ec.embedding <=> query_embedding) > umbral
  ORDER BY ec.embedding <=> query_embedding
  LIMIT limite;
END;
$$ LANGUAGE plpgsql;

-- Refresh de vistas materializadas
CREATE OR REPLACE FUNCTION refresh_vistas_materializadas()
RETURNS VOID AS $$
BEGIN
  REFRESH MATERIALIZED VIEW CONCURRENTLY eventos_hoy;
END;
$$ LANGUAGE plpgsql;