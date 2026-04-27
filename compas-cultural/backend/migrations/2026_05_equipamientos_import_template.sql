-- ============================================================
-- Template de import masivo para equipamientos 2026
-- Requiere migracion: 2026_05_equipamientos_zonas_ml.sql
-- ============================================================

-- 1) Reemplaza el contenido del array JSON por tu dataset completo.
-- 2) Ejecuta este script en Supabase SQL Editor.

SELECT importar_equipamientos_2026(
  $$
  [
    {
      "external_id": "SBPM-001",
      "nombre_oficial": "Biblioteca Publica Piloto - Sede Central",
      "slug": "biblioteca-publica-piloto-sede-central",
      "grupo": "bibliotecas_sbpm",
      "subtipo": "Biblioteca patrimonial",
      "operador": "Biblioteca Publica Piloto",
      "municipio": "medellin",
      "comuna": "11 Laureles Estadio",
      "barrio": "Carlos E Restrepo",
      "direccion": "Cra 64 #50-32",
      "web": "https://bibliotecapiloto.gov.co",
      "facebook": "/BibliotecaPublicaPiloto",
      "instagram": "@bibliotecapiloto",
      "telefono": "(604) 460 0590",
      "correo": "direccion@bibliotecapiloto.gov.co",
      "horario": "L-V 8:30-19:00; Sab 9:00-18:00",
      "aforo_texto": "Auditorio mayor + salas",
      "categorias": ["libreria", "cine", "musica", "teatro", "centro_cultural"],
      "estado_operativo": "vigente",
      "observaciones": "Activa. Patrimonio bibliografico de Antioquia.",
      "fuente_principal": "https://bibliotecapiloto.gov.co",
      "fuentes_secundarias": ["https://bibliotecasmedellin.gov.co"],
      "ultima_verificacion": "2026-04-27",
      "metadata": {"dataset":"equipamientos_medellin_2026"}
    },
    {
      "external_id": "TEA-003",
      "nombre_oficial": "Teatro Lido",
      "slug": "teatro-lido",
      "grupo": "teatros_y_escenicos",
      "subtipo": "Teatro oficial",
      "operador": "Distrito de Medellin",
      "municipio": "medellin",
      "comuna": "10 La Candelaria",
      "barrio": "Villanueva",
      "direccion": "Cra 48 #54-20",
      "web": "https://medellin.gov.co",
      "categorias": ["teatro", "musica", "cine"],
      "estado_operativo": "restauracion",
      "observaciones": "Cerrado por restauracion. Reapertura estimada 2027.",
      "fuente_principal": "https://medellin.gov.co",
      "ultima_verificacion": "2026-04-27",
      "metadata": {"dataset":"equipamientos_medellin_2026"}
    },
    {
      "external_id": "UVA-012",
      "nombre_oficial": "UVA Ilusion Verde",
      "slug": "uva-ilusion-verde",
      "grupo": "uvas_y_analogos",
      "subtipo": "UVA EPM",
      "operador": "Fundacion EPM",
      "municipio": "medellin",
      "comuna": "14 El Poblado",
      "barrio": "Los Naranjos",
      "direccion": "Cl 3B Sur #29B-56",
      "web": "https://grupo-epm.com",
      "categorias": ["centro_cultural", "teatro", "danza", "musica", "cine"],
      "estado_operativo": "vigente",
      "observaciones": "UVA activa con oferta cultural y recreativa.",
      "fuente_principal": "https://grupo-epm.com/site/fundacionepm",
      "ultima_verificacion": "2026-04-27",
      "metadata": {"dataset":"equipamientos_medellin_2026"}
    }
  ]
  $$::jsonb
) AS total_importados;

-- Verificacion rapida
SELECT *
FROM oferta_cultural_por_zona_2026
ORDER BY equipamientos_activos DESC, equipamientos_total DESC
LIMIT 30;
