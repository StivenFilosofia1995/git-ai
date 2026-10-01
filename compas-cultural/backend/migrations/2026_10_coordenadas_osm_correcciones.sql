-- ════════════════════════════════════════════════════════════════════════
-- 2026-10 · Correcciones de coordenadas de lugares verificadas contra OpenStreetMap
-- Generado por la verificación del 2026-10-01 (reglas de app/services/geo_verificacion.py:
-- nombre coincide ≥75 %, no es zona administrativa, mismo municipio, sin ambigüedad).
-- Ejecutar DESPUÉS de 2026_10_coordenadas_verificadas.sql. Idempotente.
-- Resumen: {'sin_verificar': 270, 'ok': 2, 'ambiguo': 60, 'corregir': 11, 'placeholder': 15, 'nuevo': 7, 'manual': 4}
-- ════════════════════════════════════════════════════════════════════════
BEGIN;
UPDATE public.lugares SET coords_estado = 'ok', coords_fuente = 'osm:node/7007036685', coords_verificadas_en = now() WHERE id = '25739612-a289-4da4-88ba-9dcf73e5e97b';  -- Casa Kolacho
-- El Club del Jazz → OSM «El Club del Jazz» (estaba a 319 m)
UPDATE public.lugares SET lat = 6.2506021, lng = -75.5624821, coords_estado = 'corregir', coords_fuente = 'osm:node/12666567001', coords_verificadas_en = now() WHERE id = 'd41965cd-bb7b-4a08-9e10-fa4705f0a845';
-- Festival Internacional de Poesía de Medellín: coordenada de relleno (centro de Medellín) → se borra
UPDATE public.lugares SET lat = NULL, lng = NULL, coords_estado = 'placeholder', coords_verificadas_en = now() WHERE id = '88bddf56-0e98-4411-9a61-9211ce49b692';
UPDATE public.lugares SET coords_estado = 'ok', coords_fuente = 'osm:node/1650634115', coords_verificadas_en = now() WHERE id = 'a203a831-d534-459b-abfa-83a984875d34';  -- Casa Tres Patios
-- Teatro El Trueque → OSM «Teatro El Trueque» (estaba a 569 m)
UPDATE public.lugares SET lat = 6.2469824, lng = -75.5597588, coords_estado = 'corregir', coords_fuente = 'osm:node/1718442715', coords_verificadas_en = now() WHERE id = 'b873a2bf-30ef-4849-a99d-70c554f7d2ed';
-- Burdo → OSM «Burdo» (estaba a 288 m)
UPDATE public.lugares SET lat = 6.2084572, lng = -75.5657929, coords_estado = 'corregir', coords_fuente = 'osm:node/4209578899', coords_verificadas_en = now() WHERE id = '8955c01b-78d1-4c1d-860f-8606b4de0c03';
-- Acción Impro → OSM «Acción Impro» (sin coordenadas)
UPDATE public.lugares SET lat = 6.2104340, lng = -75.5721643, coords_estado = 'nuevo', coords_fuente = 'osm:node/6732179986', coords_verificadas_en = now() WHERE id = '019e33b4-767b-42ac-a2fa-ba1129d5d1a9';
-- Club Líbido: coordenada de relleno (centro de Medellín) → se borra
UPDATE public.lugares SET lat = NULL, lng = NULL, coords_estado = 'placeholder', coords_verificadas_en = now() WHERE id = '898bc440-c48d-4f4a-b15f-efa40c61cfab';
-- La Maldita Vecindad: coordenada de relleno (centro de Medellín) → se borra
UPDATE public.lugares SET lat = NULL, lng = NULL, coords_estado = 'placeholder', coords_verificadas_en = now() WHERE id = 'cb19f611-86ee-40fc-970c-c23337f37b90';
-- Casa de la Cultura La Barquereña → OSM «Casa de la cultura La BARQUEREÑA» (sin coordenadas)
UPDATE public.lugares SET lat = 6.1502889, lng = -75.6123985, coords_estado = 'nuevo', coords_fuente = 'osm:way/134548686', coords_verificadas_en = now() WHERE id = '8a22c6fd-0656-4254-9179-a68dedeca1b9';
-- Pequeño Teatro de Medellín → OSM «Pequeño Teatro» (estaba a 815 m)
UPDATE public.lugares SET lat = 6.2474759, lng = -75.5616526, coords_estado = 'corregir', coords_fuente = 'osm:node/4326400489', coords_verificadas_en = now() WHERE id = 'e7475d19-6b60-4ac2-9d63-fb75de6f6dff';
-- UVA La Imaginación → OSM «UVA de la Imaginacion» (sin coordenadas)
UPDATE public.lugares SET lat = 6.2528126, lng = -75.5557524, coords_estado = 'nuevo', coords_fuente = 'osm:node/4588628100', coords_verificadas_en = now() WHERE id = '6e3a1125-f73d-4c48-9f1a-9ea1bf7a9aea';
-- Festival Internacional de Teatro de Medellín: coordenada de relleno (centro de Medellín) → se borra
UPDATE public.lugares SET lat = NULL, lng = NULL, coords_estado = 'placeholder', coords_verificadas_en = now() WHERE id = '62b37626-bf0a-48c7-ba00-d25c06357de4';
-- Instituto de Artes de Medellín IDAM: coordenada de relleno (centro de Medellín) → se borra
UPDATE public.lugares SET lat = NULL, lng = NULL, coords_estado = 'placeholder', coords_verificadas_en = now() WHERE id = 'ff0affbb-fe61-4590-b689-13db502a244b';
-- Accion Impro → OSM «Acción Impro» (estaba a 4713 m)
UPDATE public.lugares SET lat = 6.2104340, lng = -75.5721643, coords_estado = 'corregir', coords_fuente = 'osm:node/6732179986', coords_verificadas_en = now() WHERE id = 'eb5c95c8-2f0a-4eac-8d0e-e8962fb6d37d';
-- Águila Descalza → OSM «El Águila Descalza» (sin coordenadas)
UPDATE public.lugares SET lat = 6.2549729, lng = -75.5605686, coords_estado = 'nuevo', coords_fuente = 'osm:way/109200112', coords_verificadas_en = now() WHERE id = '66201128-ed9a-49eb-bd2e-cb87f315ad5c';
-- Teatro Matacandelas → OSM «Teatro Matacandelas» (estaba a 559 m)
UPDATE public.lugares SET lat = 6.2445086, lng = -75.5645847, coords_estado = 'corregir', coords_fuente = 'osm:node/1718445071', coords_verificadas_en = now() WHERE id = '3e6798a8-bfff-47af-9bf8-02f83a59aee0';
-- Pequeño Teatro → OSM «Pequeño Teatro» (sin coordenadas)
UPDATE public.lugares SET lat = 6.2474759, lng = -75.5616526, coords_estado = 'nuevo', coords_fuente = 'osm:node/4326400489', coords_verificadas_en = now() WHERE id = '7c4ed849-5584-4676-96f1-823a9674783c';
-- Festival Altavoz: coordenada de relleno (centro de Medellín) → se borra
UPDATE public.lugares SET lat = NULL, lng = NULL, coords_estado = 'placeholder', coords_verificadas_en = now() WHERE id = '8c50ab14-01ff-4db5-98a5-2b4c9ecc2e98';
-- Café Velvet → OSM «Café velvet» (sin coordenadas)
UPDATE public.lugares SET lat = 6.2080139, lng = -75.5669822, coords_estado = 'nuevo', coords_fuente = 'osm:node/4740267424', coords_verificadas_en = now() WHERE id = 'fe995054-f937-4644-badc-ef30267f60a6';
-- Museo de Antioquia → OSM «Museo de Antioquia» (estaba a 458 m)
UPDATE public.lugares SET lat = 6.2524079, lng = -75.5691446, coords_estado = 'corregir', coords_fuente = 'osm:way/28770080', coords_verificadas_en = now() WHERE id = '9d95908c-1519-437a-986e-bb8f7a8c9cbb';
-- Sistema de Bibliotecas Públicas de Medellín: coordenada de relleno (centro de Medellín) → se borra
UPDATE public.lugares SET lat = NULL, lng = NULL, coords_estado = 'placeholder', coords_verificadas_en = now() WHERE id = '7dcfd0b7-b1f5-4830-8a5b-b670ad88bfc7';
-- Institución Maestro Guillermo Vélez Vélez → OSM «Institución Maestro Guillermo Vélez Vélez» (sin coordenadas)
UPDATE public.lugares SET lat = 6.2817391, lng = -75.5627752, coords_estado = 'nuevo', coords_fuente = 'osm:way/834262311', coords_verificadas_en = now() WHERE id = 'a509cfcb-c641-4621-accc-905f6324a52c';
-- Festival Estéreo Picnic Medellín: coordenada de relleno (centro de Medellín) → se borra
UPDATE public.lugares SET lat = NULL, lng = NULL, coords_estado = 'placeholder', coords_verificadas_en = now() WHERE id = '3d38e0bf-fd73-4f8e-ab76-3521bb94eb9a';
-- Feria de las Flores Medellín: coordenada de relleno (centro de Medellín) → se borra
UPDATE public.lugares SET lat = NULL, lng = NULL, coords_estado = 'placeholder', coords_verificadas_en = now() WHERE id = '23e1e3dd-1605-49e1-82ec-b288a7482ec3';
-- Medellín Music Week: coordenada de relleno (centro de Medellín) → se borra
UPDATE public.lugares SET lat = NULL, lng = NULL, coords_estado = 'placeholder', coords_verificadas_en = now() WHERE id = '34987ecc-d04f-4b47-946a-91b5a91659f3';
-- Festival Urbano de Medellín: coordenada de relleno (centro de Medellín) → se borra
UPDATE public.lugares SET lat = NULL, lng = NULL, coords_estado = 'placeholder', coords_verificadas_en = now() WHERE id = '07c831d1-df42-4158-a098-f513fb49c51f';
-- Medellin Street Art Festival: coordenada de relleno (centro de Medellín) → se borra
UPDATE public.lugares SET lat = NULL, lng = NULL, coords_estado = 'placeholder', coords_verificadas_en = now() WHERE id = 'f9e7a962-e2b6-4405-bd57-ab8087406a58';
-- Miau Festival: coordenada de relleno (centro de Medellín) → se borra
UPDATE public.lugares SET lat = NULL, lng = NULL, coords_estado = 'placeholder', coords_verificadas_en = now() WHERE id = '427c918b-0737-4228-bf75-51da38eff147';
-- Biblioteca EPM → OSM «Biblioteca EPM» (estaba a 426 m)
UPDATE public.lugares SET lat = 6.2465500, lng = -75.5730812, coords_estado = 'corregir', coords_fuente = 'osm:way/32474558', coords_verificadas_en = now() WHERE id = '4e28db87-9f35-4174-9f6d-eb5a69f7909d';
-- Biblored Medellín Parques Biblioteca: coordenada de relleno (centro de Medellín) → se borra
UPDATE public.lugares SET lat = NULL, lng = NULL, coords_estado = 'placeholder', coords_verificadas_en = now() WHERE id = 'c971461d-9c69-4d6f-8df5-b7ed03af4789';
-- Biblioteca España → OSM «Parque Biblioteca España» (estaba a 644 m)
UPDATE public.lugares SET lat = 6.2946945, lng = -75.5441955, coords_estado = 'corregir', coords_fuente = 'osm:relation/6160599', coords_verificadas_en = now() WHERE id = 'df4e1a2d-6ccf-4de8-b43f-9466fc3c1848';
-- Museo Etnográfico Miguel Ángel Builes → OSM «Museo Etnográfico Miguel Ángel Builes» (estaba a 1903 m)
UPDATE public.lugares SET lat = 6.2674583, lng = -75.5971503, coords_estado = 'corregir', coords_fuente = 'osm:node/4951652613', coords_verificadas_en = now() WHERE id = '7bffa9bc-30b0-4709-8251-6f7faf5a913c';
-- UVA de la Cordialidad → OSM «UVA de la Cordialidad» (estaba a 1338 m)
UPDATE public.lugares SET lat = 6.2987709, lng = -75.5463019, coords_estado = 'corregir', coords_fuente = 'osm:node/4588274494', coords_verificadas_en = now() WHERE id = '2ad556c7-3f2b-41b8-abba-154a6d9f63a1';
-- Colectivo Ruta Maestra: coordenada de relleno (centro de Medellín) → se borra
UPDATE public.lugares SET lat = NULL, lng = NULL, coords_estado = 'placeholder', coords_verificadas_en = now() WHERE id = '74804cfd-6cdd-420a-9a97-cc93814faaa7';

-- Verdad de terreno (seeds/data/coordenadas_verificadas.json): verificadas a mano
-- Biblioteca Pública Piloto de Medellín para América Latina (sede principal, Carlos E. Restrepo) (osm:node/4444344887)
UPDATE public.lugares SET lat = 6.2554386, lng = -75.5775126, direccion = COALESCE('Carrera 64 # 50-32, Medellín', direccion), coords_estado = 'manual', coords_fuente = 'osm:node/4444344887', coords_verificadas_en = now() WHERE id IN ('055271c7-f7f2-4795-bba2-8ad6d08a25bd', '62bfd95b-5c0e-4e8f-9d75-8c4db36418fb', '46c2e6b6-90b3-4d32-b573-29d755aaeee1', '687f925b-5f2d-49f4-a6a9-899f7d4f7dd2');

-- Los eventos heredan las coordenadas corregidas de su lugar
UPDATE public.eventos e SET lat = l.lat, lng = l.lng FROM public.lugares l
WHERE e.espacio_id = l.id AND l.coords_estado IN ('corregir', 'nuevo', 'placeholder', 'manual')
  AND (e.lat IS DISTINCT FROM l.lat OR e.lng IS DISTINCT FROM l.lng);
COMMIT;
