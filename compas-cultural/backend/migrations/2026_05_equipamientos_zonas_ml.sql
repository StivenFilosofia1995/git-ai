-- ============================================================
-- Equipamientos culturales 2026 + Zonas ML
-- Objetivo:
-- 1) Cargar equipamientos culturales validados 2026
-- 2) Estandarizar mapeo barrio -> zona
-- 3) Sincronizar automaticamente con tabla lugares
-- 4) Mejorar cobertura de oferta por zona para ranking ML/scraping
-- ============================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- ------------------------------------------------------------
-- Helpers
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION norm_text(v text)
RETURNS text
LANGUAGE sql
STABLE
AS $$
  SELECT trim(regexp_replace(unaccent(lower(coalesce(v, ''))), '\\s+', ' ', 'g'));
$$;

CREATE OR REPLACE FUNCTION set_updated_at_timestamp()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;

-- ------------------------------------------------------------
-- Tabla principal de equipamientos 2026
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS equipamientos_culturales_2026 (
  id bigserial PRIMARY KEY,
  external_id text,
  nombre_oficial text NOT NULL,
  slug text NOT NULL UNIQUE,
  grupo text NOT NULL,
  subtipo text,
  operador text,

  municipio text NOT NULL DEFAULT 'medellin',
  zona_slug text,
  comuna text,
  barrio text,
  direccion text,
  lat double precision,
  lng double precision,

  web text,
  facebook text,
  instagram text,
  telefono text,
  correo text,

  horario text,
  aforo_texto text,
  categorias text[] NOT NULL DEFAULT '{}',
  estado_operativo text NOT NULL DEFAULT 'vigente',

  observaciones text,
  fuente_principal text,
  fuentes_secundarias text[] NOT NULL DEFAULT '{}',
  ultima_verificacion date,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,

  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT chk_equipamientos_grupo CHECK (
    grupo IN ('bibliotecas_sbpm', 'uvas_y_analogos', 'teatros_y_escenicos')
  ),
  CONSTRAINT chk_equipamientos_estado CHECK (
    estado_operativo IN ('vigente', 'reapertura', 'en_obra', 'restauracion', 'fuera_servicio', 'cerrado', 'proyectado')
  )
);

CREATE INDEX IF NOT EXISTS idx_equip_2026_municipio ON equipamientos_culturales_2026 (lower(municipio));
CREATE INDEX IF NOT EXISTS idx_equip_2026_barrio ON equipamientos_culturales_2026 (lower(barrio));
CREATE INDEX IF NOT EXISTS idx_equip_2026_zona ON equipamientos_culturales_2026 (zona_slug);
CREATE INDEX IF NOT EXISTS idx_equip_2026_grupo_estado ON equipamientos_culturales_2026 (grupo, estado_operativo);
CREATE INDEX IF NOT EXISTS idx_equip_2026_categorias ON equipamientos_culturales_2026 USING GIN (categorias);
CREATE INDEX IF NOT EXISTS idx_equip_2026_search ON equipamientos_culturales_2026
USING GIN (to_tsvector('spanish', coalesce(nombre_oficial,'') || ' ' || coalesce(observaciones,'') || ' ' || coalesce(direccion,'')));

DROP TRIGGER IF EXISTS trg_equip_2026_updated_at ON equipamientos_culturales_2026;
CREATE TRIGGER trg_equip_2026_updated_at
BEFORE UPDATE ON equipamientos_culturales_2026
FOR EACH ROW
EXECUTE FUNCTION set_updated_at_timestamp();

-- ------------------------------------------------------------
-- Mapeo barrio -> zona
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS zonas_barrios_map (
  id bigserial PRIMARY KEY,
  municipio text NOT NULL,
  zona_slug text NOT NULL,
  zona_nombre text NOT NULL,
  comuna text,
  barrio_alias text NOT NULL,
  barrio_alias_norm text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (municipio, zona_slug, barrio_alias_norm)
);

CREATE INDEX IF NOT EXISTS idx_zbm_municipio_alias ON zonas_barrios_map (municipio, barrio_alias_norm);
CREATE INDEX IF NOT EXISTS idx_zbm_zona ON zonas_barrios_map (zona_slug);

-- ------------------------------------------------------------
-- Canon de zonas para cobertura total (Medellin + AMVA)
-- ------------------------------------------------------------

INSERT INTO zonas_culturales (nombre, slug, descripcion, vocacion, municipio)
VALUES
  ('Popular (Comuna 1)', 'popular-comuna-1', 'Comuna 1 de Medellin', 'Hip hop, arte comunitario, bibliotecas', 'medellin'),
  ('Santa Cruz (Comuna 2)', 'santa-cruz-comuna-2', 'Comuna 2 de Medellin', 'Teatro comunitario y cultura barrial', 'medellin'),
  ('Manrique (Comuna 3)', 'manrique-comuna-3', 'Comuna 3 de Medellin', 'Arte urbano y cultura popular', 'medellin'),
  ('Aranjuez (Comuna 4)', 'aranjuez-comuna-4', 'Comuna 4 de Medellin', 'Hip hop, freestyle y memoria', 'medellin'),
  ('Castilla (Comuna 5)', 'castilla-comuna-5', 'Comuna 5 de Medellin', 'Musica y cultura barrial', 'medellin'),
  ('Doce de Octubre (Comuna 6)', 'doce-de-octubre-comuna-6', 'Comuna 6 de Medellin', 'Rap, arte urbano y cultura juvenil', 'medellin'),
  ('Robledo (Comuna 7)', 'robledo-comuna-7', 'Comuna 7 de Medellin', 'Universidad, arte y musica', 'medellin'),
  ('Villa Hermosa (Comuna 8)', 'villa-hermosa-comuna-8', 'Comuna 8 de Medellin', 'Teatro, musica y arte comunitario', 'medellin'),
  ('Buenos Aires (Comuna 9)', 'buenos-aires-comuna-9', 'Comuna 9 de Medellin', 'Arte alternativo y centros culturales', 'medellin'),
  ('La Candelaria (Comuna 10)', 'la-candelaria-comuna-10', 'Comuna 10 de Medellin', 'Museos, teatros, patrimonio', 'medellin'),
  ('Laureles Estadio (Comuna 11)', 'laureles-estadio-comuna-11', 'Comuna 11 de Medellin', 'Teatros y musica en vivo', 'medellin'),
  ('La America (Comuna 12)', 'la-america-comuna-12', 'Comuna 12 de Medellin', 'Bibliotecas y cultura vecinal', 'medellin'),
  ('San Javier (Comuna 13)', 'san-javier-comuna-13', 'Comuna 13 de Medellin', 'Grafiti, hip hop, turismo cultural', 'medellin'),
  ('El Poblado (Comuna 14)', 'el-poblado-comuna-14', 'Comuna 14 de Medellin', 'Galerias y vida cultural nocturna', 'medellin'),
  ('Guayabal (Comuna 15)', 'guayabal-comuna-15', 'Comuna 15 de Medellin', 'Escena emergente y oferta mixta', 'medellin'),
  ('Belen (Comuna 16)', 'belen-comuna-16', 'Comuna 16 de Medellin', 'Parques, bibliotecas y cultura familiar', 'medellin'),
  ('San Sebastian de Palmitas', 'san-sebastian-de-palmitas', 'Corregimiento de Medellin', 'Ruralidad y cultura campesina', 'medellin'),
  ('San Cristobal', 'san-cristobal-corregimiento', 'Corregimiento de Medellin', 'Cultura afro, hip hop y musica', 'medellin'),
  ('Altavista', 'altavista-corregimiento', 'Corregimiento de Medellin', 'Arte comunitario y naturaleza', 'medellin'),
  ('San Antonio de Prado', 'san-antonio-de-prado-corregimiento', 'Corregimiento de Medellin', 'Cultura vecinal y crecimiento urbano', 'medellin'),
  ('Santa Elena', 'santa-elena-corregimiento', 'Corregimiento de Medellin', 'Silleteros, cultura campesina, ecoturismo', 'medellin'),
  ('Bello Centro', 'bello-centro', 'Zona central de Bello', 'Cultura municipal y eventos institucionales', 'bello'),
  ('Bello Norte', 'bello-norte', 'Zona norte de Bello', 'Cultura emergente', 'bello'),
  ('Envigado Centro', 'envigado-centro', 'Zona central de Envigado', 'Filosofia, cafes culturales y patrimonio', 'envigado'),
  ('Envigado Sur', 'envigado-sur', 'Zona sur de Envigado', 'Cultura vecinal y residencial', 'envigado'),
  ('Itagui Centro', 'itagui-centro', 'Zona central de Itagui', 'Casa de la Cultura y eventos municipales', 'itagui'),
  ('Itagui Sur', 'itagui-sur', 'Zona sur de Itagui', 'Escena emergente y oferta industrial cultural', 'itagui'),
  ('Sabaneta', 'sabaneta', 'Municipio de Sabaneta', 'Gastronomia y cultura local', 'sabaneta'),
  ('La Estrella', 'la-estrella', 'Municipio de La Estrella', 'Cultura municipal y eventos al aire libre', 'la_estrella'),
  ('Caldas', 'caldas', 'Municipio de Caldas', 'Tradicion y cultura campesina', 'caldas'),
  ('Copacabana', 'copacabana', 'Municipio de Copacabana', 'Tradicion religiosa y cultura vecinal', 'copacabana'),
  ('Girardota', 'girardota', 'Municipio de Girardota', 'Turismo cultural y religiosidad', 'girardota'),
  ('Barbosa', 'barbosa', 'Municipio de Barbosa', 'Ruralidad y tradicion', 'barbosa')
ON CONFLICT (slug) DO UPDATE
SET
  nombre = EXCLUDED.nombre,
  municipio = EXCLUDED.municipio,
  vocacion = EXCLUDED.vocacion,
  descripcion = COALESCE(zonas_culturales.descripcion, EXCLUDED.descripcion);

-- ------------------------------------------------------------
-- Seed base de alias de barrios por zona
-- ------------------------------------------------------------

WITH zona_seed AS (
  SELECT * FROM (VALUES
    ('medellin','popular-comuna-1','Popular (Comuna 1)','1 Popular','Santo Domingo Savio,Granizal,Popular,Moscu,Villa Guadalupe,San Pablo,La Esperanza,Carpinelo'),
    ('medellin','santa-cruz-comuna-2','Santa Cruz (Comuna 2)','2 Santa Cruz','Santa Cruz,La Rosa,Moscu No 2,Villa del Socorro,Andalucia,La Francia,Pablo VI'),
    ('medellin','manrique-comuna-3','Manrique (Comuna 3)','3 Manrique','Manrique,La Salle,Las Granjas,Campo Valdes,El Raizal,El Pomar,Versalles'),
    ('medellin','aranjuez-comuna-4','Aranjuez (Comuna 4)','4 Aranjuez','Aranjuez,Berlin,San Isidro,Palermo,Bermejal,Moravia,Sevilla,San Pedro,Las Esmeraldas,Miranda'),
    ('medellin','castilla-comuna-5','Castilla (Comuna 5)','5 Castilla','Castilla,Alfonso Lopez,Francisco Antonio Zea,Belalcazar,Girardot,Tricentenario,Caribe,Toscana,Las Brisas,Boyaca'),
    ('medellin','doce-de-octubre-comuna-6','Doce de Octubre (Comuna 6)','6 Doce de Octubre','Doce de Octubre,Santander,Pedregal,Kennedy,Picacho,Mirador del Doce,Progreso,El Triunfo'),
    ('medellin','robledo-comuna-7','Robledo (Comuna 7)','7 Robledo','Robledo,Aures,Bello Horizonte,Villa Flora,Palenque,San German,Lopez de Mesa,Cucaracho,Pilarica,El Diamante'),
    ('medellin','villa-hermosa-comuna-8','Villa Hermosa (Comuna 8)','8 Villa Hermosa','Villa Hermosa,La Mansion,San Antonio,Enciso,Sucre,La Libertad,San Miguel,Llanaditas,La Ladera'),
    ('medellin','buenos-aires-comuna-9','Buenos Aires (Comuna 9)','9 Buenos Aires','Buenos Aires,Miraflores,Cataluna,La Milagrosa,Loreto,Bombona,Alejandro Echavarria,Juan Pablo II,El Salvador,Avila'),
    ('medellin','la-candelaria-comuna-10','La Candelaria (Comuna 10)','10 La Candelaria','La Candelaria,Villanueva,San Benito,Guayaquil,Corazon de Jesus,Calle Nueva,Perpetuo Socorro,San Diego,Boston,Los Angeles,Prado,Jesus Nazareno,La Alpujarra,San Ignacio'),
    ('medellin','laureles-estadio-comuna-11','Laureles Estadio (Comuna 11)','11 Laureles Estadio','Laureles,Estadio,Los Conquistadores,San Joaquin,Bolivariana,Velodromo,Florida Nueva,Naranjal,Suramericana,Carlos E Restrepo,Laureles Estadio'),
    ('medellin','la-america-comuna-12','La America (Comuna 12)','12 La America','La America,La Floresta,Santa Lucia,Simon Bolivar,Santa Monica,Calasanz,Ferrini,Cristobal,La Castellana'),
    ('medellin','san-javier-comuna-13','San Javier (Comuna 13)','13 San Javier','San Javier,Veinte de Julio,El Socorro,La Independencia,Nuevos Conquistadores,El Salado,Las Independencias,Comuna 13,Campo Alegre'),
    ('medellin','el-poblado-comuna-14','El Poblado (Comuna 14)','14 El Poblado','El Poblado,Manila,Astorga,Patio Bonito,La Aguacatala,El Tesoro,Los Naranjos,Provenza,Lleras,San Lucas,Ciudad del Rio,Lalinde'),
    ('medellin','guayabal-comuna-15','Guayabal (Comuna 15)','15 Guayabal','Guayabal,Trinidad,Santa Fe,Cristo Rey,Campo Amor,Noel,La Colina'),
    ('medellin','belen-comuna-16','Belen (Comuna 16)','16 Belen','Belen,La Palma,Las Violetas,Rosales,Fatima,La Nubia,Rodeo Alto,San Bernardo,Las Playas,La Gloria,La Mota,El Rincon,Los Alpes,Granada,Belen Los Alpes,San Bernardo'),
    ('medellin','san-cristobal-corregimiento','San Cristobal',NULL,'San Cristobal,Pajarito,La Loma,El Llano,Travesias,Pedregal Alto,Lusitania,Nuevo Occidente,La Aurora'),
    ('medellin','san-antonio-de-prado-corregimiento','San Antonio de Prado',NULL,'San Antonio de Prado,El Limonar,El Vergel,Cabecera SAP,Pradito'),
    ('medellin','santa-elena-corregimiento','Santa Elena',NULL,'Santa Elena,Piedras Blancas,Media Luna,Mazo,El Cerro'),
    ('medellin','altavista-corregimiento','Altavista',NULL,'Altavista,Centralidad Altavista,Aguas Frias,San Jose del Manzanillo'),
    ('medellin','san-sebastian-de-palmitas','San Sebastian de Palmitas',NULL,'Palmitas,Parte Central,La Volcana,La Aldea,Urquita'),
    ('bello','bello-centro','Bello Centro',NULL,'Bello Centro,Niquia,Paris,Zamora,La Madera,Espiritu Santo,Panamericano'),
    ('bello','bello-norte','Bello Norte',NULL,'Trapiche,Hato Viejo,La Camila,Tierra Adentro,Ciudadela del Norte'),
    ('envigado','envigado-centro','Envigado Centro',NULL,'Envigado Centro,Alcala,La Paz,Obrero,La Magnolia,Mesa,Villagrande'),
    ('envigado','envigado-sur','Envigado Sur',NULL,'Zuniga,El Dorado,El Portal,La Mina,El Esmeraldal,San Jose,El Trianon,Loma del Escobero'),
    ('itagui','itagui-centro','Itagui Centro',NULL,'Itagui Centro,Santa Maria,San Pio,Bariloche,Asturias,La Independencia,San Fernando,Ditaires'),
    ('itagui','itagui-sur','Itagui Sur',NULL,'Ditaires,La Finca,Los Gomez,El Ajizal,Suramerica,Villa Paula'),
    ('sabaneta','sabaneta','Sabaneta',NULL,'Sabaneta Centro,Las Casitas,Calle Larga,Restrepo Naranjo,Maria Auxiliadora,San Rafael,Mayorca,Pan de Azucar,La Doctora'),
    ('la_estrella','la-estrella','La Estrella',NULL,'La Estrella Centro,Pueblo Viejo,La Tablaza,San Isidro,Ancon Sur,La Ferreria,Sagrado Corazon'),
    ('caldas','caldas','Caldas',NULL,'Caldas Centro,La Quiebra,La Raya,La Chuscala,Sinifana,La Valeria,Primavera'),
    ('copacabana','copacabana','Copacabana',NULL,'Copacabana Centro,Machado,El Cabuyal,La Misericordia,Yarumito,San Juan,Fatima,La Pedrera'),
    ('girardota','girardota','Girardota',NULL,'Girardota Centro,El Totumo,El Hatillo,San Andres,Manga Arriba,San Diego,El Palmar'),
    ('barbosa','barbosa','Barbosa',NULL,'Barbosa Centro,El Hatillo,Yarumito,Popalito,Nechi,Corrientes,La Playa')
  ) AS v(municipio, zona_slug, zona_nombre, comuna, barrios_csv)
)
INSERT INTO zonas_barrios_map (municipio, zona_slug, zona_nombre, comuna, barrio_alias, barrio_alias_norm)
SELECT
  z.municipio,
  z.zona_slug,
  z.zona_nombre,
  z.comuna,
  trim(b) AS barrio_alias,
  norm_text(trim(b)) AS barrio_alias_norm
FROM zona_seed z,
LATERAL regexp_split_to_table(z.barrios_csv, ',') AS b
ON CONFLICT (municipio, zona_slug, barrio_alias_norm) DO NOTHING;

-- ------------------------------------------------------------
-- Resolver zona por municipio+barrio/comuna
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION infer_zona_slug(p_municipio text, p_barrio text, p_comuna text DEFAULT NULL)
RETURNS text
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
  v_municipio text := norm_text(p_municipio);
  v_barrio text := norm_text(p_barrio);
  v_comuna text := norm_text(p_comuna);
  v_slug text;
BEGIN
  IF v_municipio = '' THEN
    v_municipio := 'medellin';
  END IF;

  SELECT zbm.zona_slug INTO v_slug
  FROM zonas_barrios_map zbm
  WHERE norm_text(zbm.municipio) = v_municipio
    AND zbm.barrio_alias_norm = v_barrio
  LIMIT 1;

  IF v_slug IS NOT NULL THEN
    RETURN v_slug;
  END IF;

  IF v_comuna <> '' THEN
    SELECT zbm.zona_slug INTO v_slug
    FROM zonas_barrios_map zbm
    WHERE norm_text(zbm.municipio) = v_municipio
      AND norm_text(coalesce(zbm.comuna, '')) = v_comuna
    LIMIT 1;

    IF v_slug IS NOT NULL THEN
      RETURN v_slug;
    END IF;
  END IF;

  RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION trg_fill_zona_slug_equip_2026()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.zona_slug IS NULL OR NEW.zona_slug = '' THEN
    NEW.zona_slug := infer_zona_slug(NEW.municipio, NEW.barrio, NEW.comuna);
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_fill_zona_slug_equip_2026 ON equipamientos_culturales_2026;
CREATE TRIGGER trg_fill_zona_slug_equip_2026
BEFORE INSERT OR UPDATE ON equipamientos_culturales_2026
FOR EACH ROW
EXECUTE FUNCTION trg_fill_zona_slug_equip_2026();

-- ------------------------------------------------------------
-- Sync a lugares (tabla consumida por app/ML)
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION sync_equipamiento_to_lugares()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_tipo text;
  v_categoria text;
  v_categorias text[];
  v_nivel_actividad text;
BEGIN
  v_tipo := 'espacio_fisico';

  IF NEW.grupo = 'teatros_y_escenicos' THEN
    v_categoria := 'teatro';
  ELSIF NEW.grupo = 'bibliotecas_sbpm' THEN
    v_categoria := 'libreria';
  ELSE
    v_categoria := 'centro_cultural';
  END IF;

  v_categorias := CASE
    WHEN coalesce(array_length(NEW.categorias, 1), 0) > 0 THEN NEW.categorias
    ELSE ARRAY[v_categoria]
  END;

  IF NEW.estado_operativo IN ('cerrado', 'fuera_servicio', 'restauracion') THEN
    v_nivel_actividad := 'cerrado';
  ELSIF NEW.estado_operativo IN ('en_obra', 'proyectado') THEN
    v_nivel_actividad := 'emergente';
  ELSE
    v_nivel_actividad := 'activo';
  END IF;

  INSERT INTO lugares (
    nombre,
    slug,
    tipo,
    categorias,
    categoria_principal,
    municipio,
    barrio,
    comuna,
    direccion,
    lat,
    lng,
    descripcion_corta,
    descripcion,
    contexto_historico,
    instagram_handle,
    sitio_web,
    telefono,
    email,
    facebook,
    nivel_actividad,
    es_institucional,
    fuente_datos,
    ultima_verificacion
  )
  VALUES (
    NEW.nombre_oficial,
    NEW.slug,
    v_tipo,
    v_categorias,
    v_categoria,
    NEW.municipio,
    NEW.barrio,
    NEW.comuna,
    NEW.direccion,
    NEW.lat,
    NEW.lng,
    substring(coalesce(NEW.observaciones, NEW.subtipo, NEW.grupo, ''), 1, 300),
    NEW.observaciones,
    CASE WHEN NEW.zona_slug IS NULL THEN NULL ELSE 'zona_slug:' || NEW.zona_slug END,
    NEW.instagram,
    NEW.web,
    NEW.telefono,
    NEW.correo,
    NEW.facebook,
    v_nivel_actividad,
    true,
    'equipamientos_2026',
    CASE WHEN NEW.ultima_verificacion IS NULL THEN NULL ELSE NEW.ultima_verificacion::timestamptz END
  )
  ON CONFLICT (slug) DO UPDATE
  SET
    nombre = EXCLUDED.nombre,
    tipo = EXCLUDED.tipo,
    categorias = EXCLUDED.categorias,
    categoria_principal = EXCLUDED.categoria_principal,
    municipio = EXCLUDED.municipio,
    barrio = EXCLUDED.barrio,
    comuna = EXCLUDED.comuna,
    direccion = EXCLUDED.direccion,
    lat = EXCLUDED.lat,
    lng = EXCLUDED.lng,
    descripcion_corta = EXCLUDED.descripcion_corta,
    descripcion = EXCLUDED.descripcion,
    contexto_historico = EXCLUDED.contexto_historico,
    instagram_handle = EXCLUDED.instagram_handle,
    sitio_web = EXCLUDED.sitio_web,
    telefono = EXCLUDED.telefono,
    email = EXCLUDED.email,
    facebook = EXCLUDED.facebook,
    nivel_actividad = EXCLUDED.nivel_actividad,
    es_institucional = EXCLUDED.es_institucional,
    fuente_datos = EXCLUDED.fuente_datos,
    ultima_verificacion = EXCLUDED.ultima_verificacion,
    updated_at = now();

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_sync_equip_2026_to_lugares ON equipamientos_culturales_2026;
CREATE TRIGGER trg_sync_equip_2026_to_lugares
AFTER INSERT OR UPDATE ON equipamientos_culturales_2026
FOR EACH ROW
EXECUTE FUNCTION sync_equipamiento_to_lugares();

-- ------------------------------------------------------------
-- Import masivo JSONB
-- payload esperado: arreglo de objetos
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION importar_equipamientos_2026(payload jsonb)
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
  r jsonb;
  inserted_count integer := 0;
BEGIN
  IF payload IS NULL OR jsonb_typeof(payload) <> 'array' THEN
    RAISE EXCEPTION 'payload debe ser un array JSON';
  END IF;

  FOR r IN SELECT * FROM jsonb_array_elements(payload)
  LOOP
    INSERT INTO equipamientos_culturales_2026 (
      external_id,
      nombre_oficial,
      slug,
      grupo,
      subtipo,
      operador,
      municipio,
      zona_slug,
      comuna,
      barrio,
      direccion,
      web,
      facebook,
      instagram,
      telefono,
      correo,
      horario,
      aforo_texto,
      categorias,
      estado_operativo,
      observaciones,
      fuente_principal,
      fuentes_secundarias,
      ultima_verificacion,
      metadata
    )
    VALUES (
      r->>'external_id',
      r->>'nombre_oficial',
      coalesce(r->>'slug', regexp_replace(norm_text(r->>'nombre_oficial'), '[^a-z0-9]+', '-', 'g')),
      coalesce(r->>'grupo', 'teatros_y_escenicos'),
      r->>'subtipo',
      r->>'operador',
      coalesce(r->>'municipio', 'medellin'),
      r->>'zona_slug',
      r->>'comuna',
      r->>'barrio',
      r->>'direccion',
      r->>'web',
      r->>'facebook',
      r->>'instagram',
      r->>'telefono',
      r->>'correo',
      r->>'horario',
      r->>'aforo_texto',
      COALESCE(
        (SELECT array_agg(value::text) FROM jsonb_array_elements_text(coalesce(r->'categorias', '[]'::jsonb))),
        ARRAY[]::text[]
      ),
      coalesce(r->>'estado_operativo', 'vigente'),
      r->>'observaciones',
      r->>'fuente_principal',
      COALESCE(
        (SELECT array_agg(value::text) FROM jsonb_array_elements_text(coalesce(r->'fuentes_secundarias', '[]'::jsonb))),
        ARRAY[]::text[]
      ),
      NULLIF(r->>'ultima_verificacion', '')::date,
      coalesce(r->'metadata', '{}'::jsonb)
    )
    ON CONFLICT (slug) DO UPDATE
    SET
      external_id = EXCLUDED.external_id,
      nombre_oficial = EXCLUDED.nombre_oficial,
      grupo = EXCLUDED.grupo,
      subtipo = EXCLUDED.subtipo,
      operador = EXCLUDED.operador,
      municipio = EXCLUDED.municipio,
      zona_slug = EXCLUDED.zona_slug,
      comuna = EXCLUDED.comuna,
      barrio = EXCLUDED.barrio,
      direccion = EXCLUDED.direccion,
      web = EXCLUDED.web,
      facebook = EXCLUDED.facebook,
      instagram = EXCLUDED.instagram,
      telefono = EXCLUDED.telefono,
      correo = EXCLUDED.correo,
      horario = EXCLUDED.horario,
      aforo_texto = EXCLUDED.aforo_texto,
      categorias = EXCLUDED.categorias,
      estado_operativo = EXCLUDED.estado_operativo,
      observaciones = EXCLUDED.observaciones,
      fuente_principal = EXCLUDED.fuente_principal,
      fuentes_secundarias = EXCLUDED.fuentes_secundarias,
      ultima_verificacion = EXCLUDED.ultima_verificacion,
      metadata = EXCLUDED.metadata,
      updated_at = now();

    inserted_count := inserted_count + 1;
  END LOOP;

  RETURN inserted_count;
END;
$$;


CREATE OR REPLACE FUNCTION clean_md_cell(v text)
RETURNS text
LANGUAGE sql
STABLE
AS $$
  SELECT NULLIF(trim(regexp_replace(replace(replace(coalesce(v, ''), '**', ''), '"', ''), '\\s+', ' ', 'g')), '');
$$;


CREATE OR REPLACE FUNCTION md_value_or_null(v text)
RETURNS text
LANGUAGE sql
STABLE
AS $$
  SELECT CASE
    WHEN clean_md_cell(v) IS NULL THEN NULL
    WHEN norm_text(clean_md_cell(v)) IN ('por verificar', 'pv', 'sin sala', 'sin sede', 'por definir') THEN NULL
    ELSE clean_md_cell(v)
  END;
$$;


CREATE OR REPLACE FUNCTION infer_municipio_md(
  p_nombre text,
  p_comuna text,
  p_zona text,
  p_observaciones text
)
RETURNS text
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
  blob text := norm_text(coalesce(p_nombre, '') || ' ' || coalesce(p_comuna, '') || ' ' || coalesce(p_zona, '') || ' ' || coalesce(p_observaciones, ''));
BEGIN
  IF blob LIKE '% itagui %' OR blob LIKE 'itagui %' OR blob LIKE '% itagui' THEN
    RETURN 'itagui';
  ELSIF blob LIKE '% bello %' OR blob LIKE 'bello %' OR blob LIKE '% bello' THEN
    RETURN 'bello';
  ELSIF blob LIKE '% envigado %' OR blob LIKE 'envigado %' OR blob LIKE '% envigado' THEN
    RETURN 'envigado';
  ELSIF blob LIKE '% sabaneta %' OR blob LIKE 'sabaneta %' OR blob LIKE '% sabaneta' THEN
    RETURN 'sabaneta';
  ELSIF blob LIKE '% copacabana %' OR blob LIKE 'copacabana %' OR blob LIKE '% copacabana' THEN
    RETURN 'copacabana';
  ELSIF blob LIKE '% girardota %' OR blob LIKE 'girardota %' OR blob LIKE '% girardota' THEN
    RETURN 'girardota';
  ELSIF blob LIKE '% barbosa %' OR blob LIKE 'barbosa %' OR blob LIKE '% barbosa' THEN
    RETURN 'barbosa';
  ELSIF blob LIKE '% la estrella %' OR blob LIKE '% la_estrella %' THEN
    RETURN 'la_estrella';
  ELSIF blob LIKE '% caldas %' OR blob LIKE 'caldas %' OR blob LIKE '% caldas' THEN
    RETURN 'caldas';
  END IF;
  RETURN 'medellin';
END;
$$;


CREATE OR REPLACE FUNCTION infer_estado_operativo_md(
  p_estado_hint text,
  p_horario text,
  p_observaciones text
)
RETURNS text
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
  blob text := norm_text(coalesce(p_estado_hint, '') || ' ' || coalesce(p_horario, '') || ' ' || coalesce(p_observaciones, ''));
BEGIN
  IF blob LIKE '%fuera de servicio%' THEN
    RETURN 'fuera_servicio';
  ELSIF blob LIKE '%cerrado%' THEN
    RETURN 'cerrado';
  ELSIF blob LIKE '%restauracion%' THEN
    RETURN 'restauracion';
  ELSIF blob LIKE '%reapertura%' OR blob LIKE '%en reapertura%' THEN
    RETURN 'reapertura';
  ELSIF blob LIKE '%en obra%' OR blob LIKE '%en construccion%' OR blob LIKE '%inicio obras%' OR blob LIKE '%inició obras%' THEN
    RETURN 'en_obra';
  ELSIF blob LIKE '%proyectado%' OR blob LIKE '%proximo a iniciar%' OR blob LIKE '%próximo a iniciar%' THEN
    RETURN 'proyectado';
  END IF;
  RETURN 'vigente';
END;
$$;


CREATE OR REPLACE FUNCTION parse_categorias_md(v text)
RETURNS text[]
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
  tok text;
  cleaned text;
  out_arr text[] := ARRAY[]::text[];
BEGIN
  IF md_value_or_null(v) IS NULL THEN
    RETURN out_arr;
  END IF;

  FOR tok IN
    SELECT trim(x)
    FROM regexp_split_to_table(coalesce(v, ''), ',') AS x
  LOOP
    cleaned := trim(regexp_replace(replace(replace(tok, '**', ''), '"', ''), '\\(.*?\\)', '', 'g'));
    IF cleaned IS NULL OR cleaned = '' THEN
      CONTINUE;
    END IF;
    out_arr := out_arr || cleaned;
  END LOOP;

  RETURN out_arr;
END;
$$;


CREATE OR REPLACE FUNCTION importar_equipamientos_2026_desde_markdown(md text)
RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE
  ln text;
  cols text[];
  current_group text := NULL;
  row_n int := 0;
  inserted_count int := 0;
  g1 int := 0;
  g2 int := 0;
  g2_analogos int := 0;
  g3 int := 0;

  v_nombre text;
  v_subtipo text;
  v_operador text;
  v_direccion text;
  v_barrio text;
  v_comuna text;
  v_zona_txt text;
  v_web text;
  v_facebook text;
  v_instagram text;
  v_telefono text;
  v_correo text;
  v_horario text;
  v_aforo text;
  v_categorias text[];
  v_observaciones text;
  v_estado text;
  v_municipio text;
  v_slug text;
BEGIN
  IF md IS NULL OR trim(md) = '' THEN
    RAISE EXCEPTION 'markdown vacio';
  END IF;

  FOR ln IN
    SELECT regexp_replace(x, E'\\r', '', 'g')
    FROM regexp_split_to_table(md, E'\\n') AS x
  LOOP
    IF ln ILIKE '## GRUPO 1%' THEN
      current_group := 'bibliotecas_sbpm';
      CONTINUE;
    ELSIF ln ILIKE '## GRUPO 2%' THEN
      current_group := 'uvas_y_analogos';
      CONTINUE;
    ELSIF ln ILIKE '## GRUPO 3%' THEN
      current_group := 'teatros_y_escenicos';
      CONTINUE;
    ELSIF ln ILIKE '### UVAS NO ejecutadas%' THEN
      current_group := 'skip';
      CONTINUE;
    ELSIF ln ILIKE '### Espacios CERRADOS / NO existentes%' THEN
      current_group := 'skip';
      CONTINUE;
    ELSIF ln ILIKE '### Espacios análogos vigentes 2026%' THEN
      current_group := 'uvas_analogos';
      CONTINUE;
    END IF;

    IF left(trim(ln), 1) <> '|' THEN
      CONTINUE;
    END IF;

    IF ln ~ '^\\|[- ]+\\|' OR ln ILIKE '%| # |%' OR ln ILIKE '%| Nombre oficial |%' OR ln ILIKE '%| Nombre | Tipo | Operador |%' THEN
      CONTINUE;
    END IF;

    cols := regexp_split_to_array(regexp_replace(trim(ln), '^\\||\\|$', '', 'g'), '\\s*\\|\\s*');
    IF cols IS NULL OR array_length(cols, 1) IS NULL THEN
      CONTINUE;
    END IF;

    IF current_group = 'uvas_analogos' THEN
      IF array_length(cols, 1) < 5 THEN
        CONTINUE;
      END IF;

      row_n := row_n + 1;
      v_nombre := md_value_or_null(cols[1]);
      v_subtipo := md_value_or_null(cols[2]);
      v_operador := md_value_or_null(cols[3]);
      v_direccion := md_value_or_null(cols[4]);
      v_estado := infer_estado_operativo_md(md_value_or_null(cols[5]), NULL, md_value_or_null(cols[5]));
      v_municipio := infer_municipio_md(v_nombre, NULL, NULL, v_direccion);
      v_slug := regexp_replace(norm_text(v_nombre), '[^a-z0-9]+', '-', 'g');

      INSERT INTO equipamientos_culturales_2026 (
        external_id, nombre_oficial, slug, grupo, subtipo, operador,
        municipio, comuna, barrio, direccion,
        estado_operativo, observaciones, fuente_principal, metadata
      ) VALUES (
        'ANLG-' || lpad(row_n::text, 3, '0'),
        v_nombre,
        v_slug,
        'uvas_y_analogos',
        v_subtipo,
        v_operador,
        v_municipio,
        NULL,
        NULL,
        v_direccion,
        v_estado,
        md_value_or_null(cols[5]),
        NULL,
        jsonb_build_object('source_format', 'markdown', 'table', 'espacios_analogos')
      )
      ON CONFLICT (slug) DO UPDATE
      SET
        grupo = EXCLUDED.grupo,
        subtipo = EXCLUDED.subtipo,
        operador = EXCLUDED.operador,
        municipio = EXCLUDED.municipio,
        direccion = EXCLUDED.direccion,
        estado_operativo = EXCLUDED.estado_operativo,
        observaciones = EXCLUDED.observaciones,
        metadata = EXCLUDED.metadata,
        updated_at = now();

      inserted_count := inserted_count + 1;
      g2_analogos := g2_analogos + 1;
      CONTINUE;
    END IF;

    IF array_length(cols, 1) < 16 OR current_group IS NULL OR current_group = 'skip' THEN
      CONTINUE;
    END IF;

    row_n := row_n + 1;

    v_nombre := md_value_or_null(cols[2]);
    v_subtipo := md_value_or_null(cols[3]);
    v_direccion := md_value_or_null(cols[4]);
    v_barrio := md_value_or_null(cols[5]);
    v_comuna := md_value_or_null(cols[6]);
    v_zona_txt := md_value_or_null(cols[7]);
    v_web := md_value_or_null(cols[8]);
    v_facebook := md_value_or_null(cols[9]);
    v_instagram := md_value_or_null(cols[10]);
    v_telefono := md_value_or_null(cols[11]);
    v_correo := md_value_or_null(cols[12]);
    v_horario := md_value_or_null(cols[13]);
    v_aforo := md_value_or_null(cols[14]);
    v_categorias := parse_categorias_md(cols[15]);
    v_observaciones := md_value_or_null(cols[16]);
    v_municipio := infer_municipio_md(v_nombre, v_comuna, v_zona_txt, v_observaciones);
    v_estado := infer_estado_operativo_md(NULL, v_horario, v_observaciones);
    v_slug := regexp_replace(norm_text(v_nombre), '[^a-z0-9]+', '-', 'g');

    IF v_slug IS NULL OR v_slug = '' OR v_nombre IS NULL THEN
      CONTINUE;
    END IF;

    IF current_group = 'bibliotecas_sbpm' THEN
      v_operador := 'SBPM/BPP';
      g1 := g1 + 1;
    ELSIF current_group = 'uvas_y_analogos' THEN
      v_operador := md_value_or_null(regexp_replace(v_subtipo, '^.*\\((.*?)\\).*$','\\1'));
      g2 := g2 + 1;
    ELSE
      v_operador := NULL;
      g3 := g3 + 1;
    END IF;

    INSERT INTO equipamientos_culturales_2026 (
      external_id,
      nombre_oficial,
      slug,
      grupo,
      subtipo,
      operador,
      municipio,
      comuna,
      barrio,
      direccion,
      web,
      facebook,
      instagram,
      telefono,
      correo,
      horario,
      aforo_texto,
      categorias,
      estado_operativo,
      observaciones,
      fuente_principal,
      metadata
    ) VALUES (
      upper(substr(current_group, 1, 3)) || '-' || lpad(row_n::text, 4, '0'),
      v_nombre,
      v_slug,
      current_group,
      v_subtipo,
      v_operador,
      v_municipio,
      v_comuna,
      v_barrio,
      v_direccion,
      CASE WHEN v_web IS NULL THEN NULL WHEN v_web ~ '^https?://' THEN v_web ELSE 'https://' || v_web END,
      v_facebook,
      v_instagram,
      v_telefono,
      v_correo,
      v_horario,
      v_aforo,
      v_categorias,
      v_estado,
      v_observaciones,
      CASE WHEN v_web IS NULL THEN NULL WHEN v_web ~ '^https?://' THEN v_web ELSE 'https://' || v_web END,
      jsonb_build_object('source_format', 'markdown', 'table_cols', array_length(cols, 1))
    )
    ON CONFLICT (slug) DO UPDATE
    SET
      external_id = EXCLUDED.external_id,
      nombre_oficial = EXCLUDED.nombre_oficial,
      grupo = EXCLUDED.grupo,
      subtipo = EXCLUDED.subtipo,
      operador = EXCLUDED.operador,
      municipio = EXCLUDED.municipio,
      comuna = EXCLUDED.comuna,
      barrio = EXCLUDED.barrio,
      direccion = EXCLUDED.direccion,
      web = EXCLUDED.web,
      facebook = EXCLUDED.facebook,
      instagram = EXCLUDED.instagram,
      telefono = EXCLUDED.telefono,
      correo = EXCLUDED.correo,
      horario = EXCLUDED.horario,
      aforo_texto = EXCLUDED.aforo_texto,
      categorias = EXCLUDED.categorias,
      estado_operativo = EXCLUDED.estado_operativo,
      observaciones = EXCLUDED.observaciones,
      fuente_principal = EXCLUDED.fuente_principal,
      metadata = EXCLUDED.metadata,
      updated_at = now();

    inserted_count := inserted_count + 1;
  END LOOP;

  RETURN jsonb_build_object(
    'total_filas_upsert', inserted_count,
    'grupo_1_bibliotecas', g1,
    'grupo_2_uvas', g2,
    'grupo_2_analogos', g2_analogos,
    'grupo_3_teatros', g3
  );
END;
$$;

-- ------------------------------------------------------------
-- Vista para scoring/observabilidad por zona
-- ------------------------------------------------------------

CREATE OR REPLACE VIEW oferta_cultural_por_zona_2026 AS
SELECT
  z.slug AS zona_slug,
  z.nombre AS zona_nombre,
  z.municipio,
  count(e.id) AS equipamientos_total,
  count(e.id) FILTER (WHERE e.estado_operativo IN ('vigente', 'reapertura')) AS equipamientos_activos,
  count(e.id) FILTER (WHERE e.grupo = 'bibliotecas_sbpm') AS total_bibliotecas,
  count(e.id) FILTER (WHERE e.grupo = 'uvas_y_analogos') AS total_uvas,
  count(e.id) FILTER (WHERE e.grupo = 'teatros_y_escenicos') AS total_escenicos
FROM zonas_culturales z
LEFT JOIN equipamientos_culturales_2026 e ON e.zona_slug = z.slug
GROUP BY z.slug, z.nombre, z.municipio;

COMMIT;
