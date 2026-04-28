"""
seed_equipamientos_publicos.py
==============================
Importa bibliotecas públicas (SBPM), UVAs (Fundación EPM + INDER)
y teatros/salas culturales de Medellín como registros en la tabla `lugares`.

Ejecutar:
    cd compas-cultural/backend
    python -m seeds.seed_equipamientos_publicos

Los registros tienen `sitio_web` e `instagram_handle` configurados para que
el auto-scraper detecte automáticamente eventos desde sus páginas.
"""

import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import supabase

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[áàäâã]", "a", text)
    text = re.sub(r"[éèëê]", "e", text)
    text = re.sub(r"[íìïî]", "i", text)
    text = re.sub(r"[óòöôõ]", "o", text)
    text = re.sub(r"[úùüû]", "u", text)
    text = re.sub(r"ñ", "n", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


# ---------------------------------------------------------------------------
# GRUPO 1 — Bibliotecas públicas (SBPM + BPP)
# ---------------------------------------------------------------------------

BIBLIOTECAS = [
    {
        "nombre": "Biblioteca Pública Piloto para América Latina",
        "tipo": "biblioteca",
        "categoria_principal": "literatura",
        "categorias": ["literatura", "taller", "cine", "patrimonio", "artes_plasticas", "musica_en_vivo"],
        "municipio": "Medellín",
        "barrio": "Carlos E. Restrepo",
        "direccion": "Cra 64 #50-32",
        "sitio_web": "https://www.bibliotecapiloto.gov.co",
        "instagram_handle": "bibliotecapiloto",
        "facebook": "BibliotecaPublicaPiloto",
        "descripcion_corta": "Principal biblioteca pública de Antioquia. Patrimonio bibliográfico con más de 140.000 referencias.",
        "nivel_actividad": "muy_activo",
    },
    {
        "nombre": "Parque Biblioteca León de Greiff – La Ladera",
        "tipo": "biblioteca",
        "categoria_principal": "literatura",
        "categorias": ["teatro", "musica_en_vivo", "danza", "artes_plasticas", "cine", "literatura", "taller"],
        "municipio": "Medellín",
        "barrio": "La Ladera",
        "sitio_web": "https://bibliotecasmedellin.gov.co/actividades/",
        "instagram_handle": "pbladera",
        "facebook": "PBLaLadera",
        "descripcion_corta": "Parque Biblioteca en antigua Cárcel Celular. Diseño Giancarlo Mazzanti.",
        "nivel_actividad": "muy_activo",
    },
    {
        "nombre": "Parque Biblioteca Tomás Carrasquilla – La Quintana",
        "tipo": "biblioteca",
        "categoria_principal": "literatura",
        "categorias": ["cine", "artes_plasticas", "taller", "literatura", "musica_en_vivo"],
        "municipio": "Medellín",
        "barrio": "López de Mesa",
        "sitio_web": "https://bibliotecasmedellin.gov.co/actividades/",
        "instagram_handle": "pblaquintana",
        "facebook": "PBLaQuintana",
        "descripcion_corta": "Parque Biblioteca en Robledo con auditorio y mirador.",
        "nivel_actividad": "muy_activo",
    },
    {
        "nombre": "Parque Biblioteca San Javier – Presbítero José Luis Arroyave",
        "tipo": "biblioteca",
        "categoria_principal": "literatura",
        "categorias": ["teatro", "musica_en_vivo", "danza", "artes_plasticas", "cine", "literatura", "taller"],
        "municipio": "Medellín",
        "barrio": "San Javier",
        "sitio_web": "https://bibliotecasmedellin.gov.co/actividades/",
        "instagram_handle": "pbsanjavier",
        "facebook": "PBSanJavier",
        "descripcion_corta": "Primer Parque Biblioteca de Medellín. Makerspace y conexión Metro San Javier.",
        "nivel_actividad": "muy_activo",
    },
    {
        "nombre": "Parque Biblioteca Belén",
        "tipo": "biblioteca",
        "categoria_principal": "literatura",
        "categorias": ["teatro", "musica_en_vivo", "danza", "cine", "literatura", "taller"],
        "municipio": "Medellín",
        "barrio": "Belén",
        "sitio_web": "https://bibliotecasmedellin.gov.co/actividades/",
        "instagram_handle": "parquebibliotecabelen",
        "facebook": "ParqueBibliotecaBelen",
        "descripcion_corta": "Diseño japonés de Hiroshi Naito. Operada por Comfenalco. Sede Distrito Otaku.",
        "nivel_actividad": "muy_activo",
    },
    {
        "nombre": "Parque Biblioteca Manuel Mejía Vallejo – Guayabal",
        "tipo": "biblioteca",
        "categoria_principal": "literatura",
        "categorias": ["teatro", "musica_en_vivo", "taller", "artes_plasticas", "cine"],
        "municipio": "Medellín",
        "barrio": "Guayabal",
        "sitio_web": "https://bibliotecasmedellin.gov.co/actividades/",
        "instagram_handle": "pbguayabal",
        "facebook": "PBGuayabal",
        "descripcion_corta": "Único PB en zona industrial. Especializado en tango y patrimonio arqueológico.",
        "nivel_actividad": "activo",
    },
    {
        "nombre": "Parque Biblioteca Gabriel García Márquez – Doce de Octubre",
        "tipo": "biblioteca",
        "categoria_principal": "literatura",
        "categorias": ["teatro", "musica_en_vivo", "danza", "taller", "literatura"],
        "municipio": "Medellín",
        "barrio": "Doce de Octubre",
        "sitio_web": "https://bibliotecasmedellin.gov.co/actividades/",
        "instagram_handle": "pbdocedeoctubre",
        "facebook": "PBDocedeOctubre",
        "descripcion_corta": "Diseño tipo periscopio con Makerspace 3D y láser.",
        "nivel_actividad": "muy_activo",
    },
    {
        "nombre": "Parque Biblioteca Fernando Botero – San Cristóbal",
        "tipo": "biblioteca",
        "categoria_principal": "literatura",
        "categorias": ["teatro", "musica_en_vivo", "taller", "literatura", "artes_plasticas"],
        "municipio": "Medellín",
        "barrio": "San Cristóbal",
        "sitio_web": "https://bibliotecasmedellin.gov.co/actividades/",
        "instagram_handle": "pbsancristobal",
        "facebook": "PBSanCristobal",
        "descripcion_corta": "Makerspace, escuela de música y estatua El Gato donada por Botero.",
        "nivel_actividad": "activo",
    },
    {
        "nombre": "Parque Biblioteca Nuevo Occidente – Lusitania",
        "tipo": "biblioteca",
        "categoria_principal": "literatura",
        "categorias": ["artes_plasticas", "cine", "taller", "literatura"],
        "municipio": "Medellín",
        "barrio": "Las Margaritas",
        "sitio_web": "https://bibliotecasmedellin.gov.co/actividades/",
        "instagram_handle": "pbnuevoocc",
        "facebook": "PBNuevoOccidenteLusitania",
        "descripcion_corta": "Décimo y más reciente Parque Biblioteca. Apertura 2021.",
        "nivel_actividad": "activo",
    },
    {
        "nombre": "Casa de la Literatura San Germán",
        "tipo": "biblioteca",
        "categoria_principal": "literatura",
        "categorias": ["literatura", "taller", "cine", "artes_plasticas", "teatro", "poesia"],
        "municipio": "Medellín",
        "barrio": "San Germán",
        "sitio_web": "https://bibliotecasmedellin.gov.co/actividades/",
        "instagram_handle": "casadelaliteraturasangerman",
        "facebook": "casadelaliteraturasangerman",
        "descripcion_corta": "Sede principal de la dirección del SBPM. Sede Hay Festival Forum 2025.",
        "nivel_actividad": "muy_activo",
    },
    {
        "nombre": "Centro de Documentación Musical El Jordán",
        "tipo": "biblioteca",
        "categoria_principal": "musica_en_vivo",
        "categorias": ["musica_en_vivo", "patrimonio", "cine", "taller", "jazz", "electronica", "rock"],
        "municipio": "Medellín",
        "barrio": "Robledo",
        "sitio_web": "https://bibliotecasmedellin.gov.co/actividades/",
        "instagram_handle": "eljordanmedellin",
        "facebook": "ElJordanMedellin",
        "descripcion_corta": "Centro de música con audiciones, conciertos y trueque musical. Sede Medellín Guitar Master.",
        "nivel_actividad": "muy_activo",
    },
    {
        "nombre": "Biblioteca Pública La Floresta",
        "tipo": "biblioteca",
        "categoria_principal": "literatura",
        "categorias": ["literatura", "musica_en_vivo", "cine", "artes_plasticas", "taller"],
        "municipio": "Medellín",
        "barrio": "La Floresta",
        "sitio_web": "https://bibliotecasmedellin.gov.co/actividades/",
        "instagram_handle": "bibliotecalafloresta",
        "facebook": "bibliotecalafloresta",
        "descripcion_corta": "Primera biblioteca de proximidad SBPM (1985). Sede Hay Festival Forum.",
        "nivel_actividad": "muy_activo",
    },
]

# ---------------------------------------------------------------------------
# GRUPO 2 — UVAs
# ---------------------------------------------------------------------------

UVAS = [
    {
        "nombre": "UVA La Imaginación",
        "tipo": "uva",
        "categoria_principal": "musica_en_vivo",
        "categorias": ["musica_en_vivo", "teatro", "artes_plasticas", "taller"],
        "municipio": "Medellín",
        "barrio": "San Miguel",
        "sitio_web": "https://www.fundacionepm.org.co/micrositios/fundacion-epm/agenda/",
        "instagram_handle": "fundacionepm",
        "descripcion_corta": "4 salas acústicas, teatro al aire libre. Premio LafargeHolcim Oro 2015.",
        "nivel_actividad": "muy_activo",
    },
    {
        "nombre": "UVA Huellas de Vida",
        "tipo": "uva",
        "categoria_principal": "musica_en_vivo",
        "categorias": ["musica_en_vivo", "teatro", "artes_plasticas", "cine", "danza", "patrimonio"],
        "municipio": "Medellín",
        "barrio": "Las Independencias",
        "sitio_web": "https://www.inder.gov.co",
        "instagram_handle": "indermedellin",
        "descripcion_corta": "Cancha acústica (230), estudio grabación, museo Comuna 13. Referente reconciliación.",
        "nivel_actividad": "muy_activo",
    },
    {
        "nombre": "UVA Sin Fronteras",
        "tipo": "uva",
        "categoria_principal": "teatro",
        "categorias": ["teatro", "danza", "artes_plasticas", "musica_en_vivo", "taller"],
        "municipio": "Medellín",
        "barrio": "Tricentenario",
        "sitio_web": "https://www.inder.gov.co",
        "instagram_handle": "uvasinfronteras",
        "descripcion_corta": "Centro Red E-Crea. Máster TV, 4.431 m² públicos.",
        "nivel_actividad": "activo",
    },
    {
        "nombre": "UVA de La Armonía",
        "tipo": "uva",
        "categoria_principal": "taller",
        "categorias": ["musica_en_vivo", "danza", "artes_plasticas", "cine", "taller"],
        "municipio": "Medellín",
        "barrio": "Bello Oriente",
        "sitio_web": "https://www.fundacionepm.org.co/micrositios/fundacion-epm/agenda/",
        "instagram_handle": "fundacionepm",
        "descripcion_corta": "Mirador panorámico Manrique. Cine al aire libre.",
        "nivel_actividad": "activo",
    },
    {
        "nombre": "UVA Ilusión Verde",
        "tipo": "uva",
        "categoria_principal": "teatro",
        "categorias": ["teatro", "musica_en_vivo", "danza", "literatura", "cine", "taller"],
        "municipio": "Medellín",
        "barrio": "Los Naranjos",
        "sitio_web": "https://www.fundacionepm.org.co/micrositios/fundacion-epm/agenda/",
        "instagram_handle": "fundacionepm",
        "descripcion_corta": "La UVA más grande (31.000 m²). Cancha sintética, biblioteca y teatro.",
        "nivel_actividad": "muy_activo",
    },
    {
        "nombre": "UVA Ciudadela Nuevo Occidente",
        "tipo": "uva",
        "categoria_principal": "teatro",
        "categorias": ["teatro", "danza", "musica_en_vivo", "cine", "taller"],
        "municipio": "Medellín",
        "barrio": "Pajarito",
        "sitio_web": "https://www.inder.gov.co",
        "instagram_handle": "indermedellin",
        "descripcion_corta": "4 módulos, piscina, auditorio cine, polideportivo. Conectada Metrocable J.",
        "nivel_actividad": "activo",
    },
    {
        "nombre": "UVA de La Esperanza",
        "tipo": "uva",
        "categoria_principal": "taller",
        "categorias": ["taller", "musica_en_vivo", "literatura", "cine"],
        "municipio": "Medellín",
        "barrio": "San Pablo",
        "sitio_web": "https://www.fundacionepm.org.co/micrositios/fundacion-epm/agenda/",
        "instagram_handle": "fundacionepm",
        "descripcion_corta": "Primera UVA inaugurada (abril 2014). 10 años en 2024.",
        "nivel_actividad": "activo",
    },
    {
        "nombre": "UVA de Los Sueños",
        "tipo": "uva",
        "categoria_principal": "musica_en_vivo",
        "categorias": ["musica_en_vivo", "artes_plasticas", "taller"],
        "municipio": "Medellín",
        "barrio": "Versalles",
        "sitio_web": "https://www.fundacionepm.org.co/micrositios/fundacion-epm/agenda/",
        "instagram_handle": "fundacionepm",
        "descripcion_corta": "Auditorio 95 personas. Tanque Versalles.",
        "nivel_actividad": "activo",
    },
]

# ---------------------------------------------------------------------------
# GRUPO 3 — Teatros y salas escénicas
# ---------------------------------------------------------------------------

TEATROS = [
    {
        "nombre": "Teatro Metropolitano de Medellín",
        "tipo": "teatro",
        "categoria_principal": "musica_en_vivo",
        "categorias": ["musica_en_vivo", "teatro", "danza", "opera", "jazz"],
        "municipio": "Medellín",
        "barrio": "La Alpujarra",
        "sitio_web": "https://www.teatrometropolitano.com",
        "instagram_handle": "teatrometropolitano",
        "facebook": "TeatroMetropolitanoMedellin",
        "descripcion_corta": "1.634 butacas. Sede Filarmónica de Medellín. Festival de Jazz y Temporada de Ópera.",
        "nivel_actividad": "muy_activo",
    },
    {
        "nombre": "Teatro Pablo Tobón Uribe",
        "tipo": "teatro",
        "categoria_principal": "teatro",
        "categorias": ["teatro", "musica_en_vivo", "danza", "cine", "literatura"],
        "municipio": "Medellín",
        "barrio": "Boston",
        "sitio_web": "https://www.teatropablotobon.com",
        "instagram_handle": "teatropablotobon",
        "facebook": "teatropablotobon",
        "descripcion_corta": "883 butacas. Patrimonio arquitectónico. Rock, metal, sinfónica, danza.",
        "nivel_actividad": "muy_activo",
    },
    {
        "nombre": "Teatro Universidad de Medellín",
        "tipo": "teatro",
        "categoria_principal": "musica_en_vivo",
        "categorias": ["musica_en_vivo", "teatro", "danza", "opera"],
        "municipio": "Medellín",
        "barrio": "Belén Los Alpes",
        "sitio_web": "https://teatro.udemedellin.edu.co",
        "instagram_handle": "teatroudem",
        "facebook": "TeatroUdeM",
        "descripcion_corta": "1.705 butacas — mayor sala de Colombia. Ópera, sinfónica, danza.",
        "nivel_actividad": "muy_activo",
    },
    {
        "nombre": "Teatro Universitario Camilo Torres Restrepo – UdeA",
        "tipo": "teatro",
        "categoria_principal": "cine",
        "categorias": ["cine", "teatro", "musica_en_vivo", "danza"],
        "municipio": "Medellín",
        "barrio": "Sevilla",
        "sitio_web": "https://www.udea.edu.co",
        "instagram_handle": "teatrocamilotorres",
        "facebook": "TeatroCamiloTorresRestrepo",
        "descripcion_corta": "1.200 butacas. 110.000 espectadores/año. Cine 35mm/16mm.",
        "nivel_actividad": "muy_activo",
    },
    {
        "nombre": "Teatro al Aire Libre Carlos Vieco Ortiz",
        "tipo": "teatro",
        "categoria_principal": "musica_en_vivo",
        "categorias": ["musica_en_vivo", "rock", "poesia", "festival"],
        "municipio": "Medellín",
        "barrio": "Nutibara",
        "sitio_web": "https://www.medellin.gov.co",
        "instagram_handle": "teatrocarlosvieco",
        "facebook": "TeatroCarlosVieco",
        "descripcion_corta": "~1.500 aforo. Templo del rock. Sede Altavoz, Mederock, Festival Poesía.",
        "nivel_actividad": "muy_activo",
    },
    {
        "nombre": "Teatro El Tesoro",
        "tipo": "teatro",
        "categoria_principal": "musica_en_vivo",
        "categorias": ["musica_en_vivo", "teatro", "danza", "jazz"],
        "municipio": "Medellín",
        "barrio": "El Poblado",
        "sitio_web": "https://www.teatroeltesoro.com",
        "instagram_handle": "teatroeltesoro",
        "facebook": "teatroeltesoro",
        "descripcion_corta": "889 butacas en Centro Comercial El Tesoro. Jazz, K-pop, sinfónica, flamenco.",
        "nivel_actividad": "muy_activo",
    },
    {
        "nombre": "Teatro Ateneo Porfirio Barba Jacob",
        "tipo": "teatro",
        "categoria_principal": "teatro",
        "categorias": ["teatro", "musica_en_vivo", "poesia", "danza", "rock"],
        "municipio": "Medellín",
        "barrio": "Bomboná",
        "sitio_web": "https://ateneomedellin.com",
        "instagram_handle": "ateneomedellin",
        "facebook": "ateneodemedellin",
        "descripcion_corta": "350 aforo. Teatro adultos, Festival Metal Medallo, monólogos, humor.",
        "nivel_actividad": "muy_activo",
    },
    {
        "nombre": "Teatro Matacandelas",
        "tipo": "teatro",
        "categoria_principal": "teatro",
        "categorias": ["teatro", "cine", "literatura", "musica_en_vivo"],
        "municipio": "Medellín",
        "barrio": "Bomboná",
        "sitio_web": "https://www.matacandelas.com",
        "instagram_handle": "matacandelas",
        "facebook": "matacandelas",
        "descripcion_corta": "Fundado 1979. Repertorio, clásicos, experimental. Cabaret El Cantadero.",
        "nivel_actividad": "muy_activo",
    },
    {
        "nombre": "Pequeño Teatro de Medellín",
        "tipo": "teatro",
        "categoria_principal": "teatro",
        "categorias": ["teatro", "literatura", "taller"],
        "municipio": "Medellín",
        "barrio": "La Candelaria",
        "sitio_web": "https://pequenoteatro.com",
        "instagram_handle": "pequeno_teatrom",
        "facebook": "pequenoteatro",
        "descripcion_corta": "450 + 78 butacas. Fundado 1975. Patrimonio Cultural.",
        "nivel_actividad": "muy_activo",
    },
    {
        "nombre": "Casa del Teatro de Medellín",
        "tipo": "teatro",
        "categoria_principal": "teatro",
        "categorias": ["teatro", "taller", "literatura"],
        "municipio": "Medellín",
        "barrio": "Prado Centro",
        "sitio_web": "https://casadelteatro.org.co",
        "instagram_handle": "casadelteatro",
        "facebook": "casadelteatro",
        "descripcion_corta": "'Casa de los estrenos'. Biblioteca Gilberto Martínez +11.000 títulos.",
        "nivel_actividad": "activo",
    },
    {
        "nombre": "Teatro El Águila Descalza",
        "tipo": "teatro",
        "categoria_principal": "teatro",
        "categorias": ["teatro", "artes_plasticas", "musica_en_vivo"],
        "municipio": "Medellín",
        "barrio": "Prado",
        "sitio_web": "https://aguiladescalza.com.co",
        "instagram_handle": "aguiladescalza",
        "facebook": "aguiladescalza",
        "descripcion_corta": "460 aforo. Humor costumbrista. Mansión patrimonial 1919.",
        "nivel_actividad": "activo",
    },
    {
        "nombre": "Casateatro El Poblado",
        "tipo": "teatro",
        "categoria_principal": "teatro",
        "categorias": ["teatro", "danza", "musica_en_vivo", "literatura"],
        "municipio": "Medellín",
        "barrio": "Santa María de los Ángeles",
        "sitio_web": "https://casateatroelpoblado.com",
        "instagram_handle": "casateatroelpoblado",
        "facebook": "CasaTeatroElPoblado",
        "descripcion_corta": "156 silletería / 220 de pie. >200 funciones/año. Café y galería.",
        "nivel_actividad": "muy_activo",
    },
    {
        "nombre": "La Pascasia",
        "tipo": "teatro",
        "categoria_principal": "musica_en_vivo",
        "categorias": ["musica_en_vivo", "jazz", "electronica", "teatro", "literatura"],
        "municipio": "Medellín",
        "barrio": "La Candelaria",
        "sitio_web": "https://lapascasia.org",
        "instagram_handle": "lapascasia",
        "facebook": "casapascasia",
        "descripcion_corta": "Auditorio ~200. Jazz, electrónica, vallenato narrado, techno. Librería y café.",
        "nivel_actividad": "muy_activo",
    },
    {
        "nombre": "Centro Cultural Comfama Aranjuez",
        "tipo": "teatro",
        "categoria_principal": "teatro",
        "categorias": ["cine", "teatro", "musica_en_vivo", "danza", "literatura"],
        "municipio": "Medellín",
        "barrio": "Aranjuez",
        "sitio_web": "https://www.comfama.com/cultura-y-ocio/centros-culturales/aranjuez",
        "instagram_handle": "comfama",
        "facebook": "comfama",
        "descripcion_corta": "272 aforo. Edificio patrimonial (antiguo manicomio 1892).",
        "nivel_actividad": "muy_activo",
    },
    {
        "nombre": "Museo de Arte Moderno de Medellín – MAMM",
        "tipo": "galeria",
        "categoria_principal": "arte_contemporaneo",
        "categorias": ["cine", "danza", "musica_en_vivo", "literatura", "arte_contemporaneo"],
        "municipio": "Medellín",
        "barrio": "Ciudad del Río",
        "sitio_web": "https://www.elmamm.org",
        "instagram_handle": "el_mamm",
        "facebook": "elmamm",
        "descripcion_corta": "256 butacas. Especializado en cine, danza y exposiciones de arte moderno.",
        "nivel_actividad": "muy_activo",
    },
    {
        "nombre": "Teatro Popular de Medellín",
        "tipo": "teatro",
        "categoria_principal": "teatro",
        "categorias": ["teatro", "musica_en_vivo", "taller"],
        "municipio": "Medellín",
        "barrio": "La Candelaria",
        "sitio_web": "https://teatropopulardemedellin.com",
        "instagram_handle": "teatrotpm",
        "facebook": "TPMTEATROPOPULAR",
        "descripcion_corta": "Fundado 1979. Patrimonio Cultural. Dramaturgia nacional y tango.",
        "nivel_actividad": "activo",
    },
    {
        "nombre": "Corporación La Polilla",
        "tipo": "teatro",
        "categoria_principal": "teatro",
        "categorias": ["teatro", "danza", "taller", "musica_en_vivo"],
        "municipio": "Medellín",
        "barrio": "Belén",
        "sitio_web": "https://lapolilla.com.co",
        "instagram_handle": "lapolillamed",
        "facebook": "lapolillamed",
        "descripcion_corta": "95 aforo. Títeres, danza, magia. Festival MIMAME. Más de 30 años.",
        "nivel_actividad": "activo",
    },
    {
        "nombre": "Corporación Cultural Nuestra Gente – La Casa Amarilla",
        "tipo": "teatro",
        "categoria_principal": "teatro",
        "categorias": ["teatro", "danza", "musica_en_vivo", "taller"],
        "municipio": "Medellín",
        "barrio": "Santa Cruz",
        "sitio_web": "https://nuestragente.com.co",
        "instagram_handle": "corporacionculturalnuestragente",
        "facebook": "corporacionculturalnuestragente",
        "descripcion_corta": "~100 sala + 200 al aire libre. Teatro comunitario barrio nororiental.",
        "nivel_actividad": "activo",
    },
    {
        "nombre": "Casa Tres Patios",
        "tipo": "galeria",
        "categoria_principal": "arte_contemporaneo",
        "categorias": ["arte_contemporaneo", "artes_plasticas", "taller"],
        "municipio": "Medellín",
        "barrio": "Prado",
        "sitio_web": "https://casatrespatios.org",
        "instagram_handle": "casatrespatios",
        "facebook": "casatrespatios",
        "descripcion_corta": "Residencias artísticas y pedagogía crítica. Coordinador Red Artes Visuales Medellín.",
        "nivel_actividad": "activo",
    },
    {
        "nombre": "Teatro Comfama – Claustro San Ignacio",
        "tipo": "teatro",
        "categoria_principal": "teatro",
        "categorias": ["teatro", "musica_en_vivo", "danza", "cine", "literatura"],
        "municipio": "Medellín",
        "barrio": "La Candelaria",
        "sitio_web": "https://www.comfama.com/cultura-y-ocio/claustro",
        "instagram_handle": "comfama",
        "facebook": "comfama",
        "descripcion_corta": "Patio Teatro ~600. Cuna primer estreno teatral Antioquia (1823).",
        "nivel_actividad": "muy_activo",
    },
]


# ---------------------------------------------------------------------------
# Import function
# ---------------------------------------------------------------------------

def upsert_equipamiento(record: dict) -> str:
    slug = slugify(record["nombre"])
    payload = {
        "slug": slug,
        "nombre": record["nombre"],
        "tipo": record.get("tipo", "espacio_cultural"),
        "categoria_principal": record.get("categoria_principal", "taller"),
        "categorias": record.get("categorias", []),
        "municipio": record.get("municipio", "Medellín"),
        "barrio": record.get("barrio"),
        "descripcion_corta": record.get("descripcion_corta"),
        "sitio_web": record.get("sitio_web"),
        "instagram_handle": record.get("instagram_handle"),
        "nivel_actividad": record.get("nivel_actividad", "activo"),
        "es_underground": False,
    }
    # Remove None values
    payload = {k: v for k, v in payload.items() if v is not None}

    try:
        supabase.table("lugares").upsert(payload, on_conflict="slug").execute()
        return f"  ✓ {record['nombre']}"
    except Exception as e:
        return f"  ✗ {record['nombre']}: {e}"


def run():
    todos = [
        ("Bibliotecas", BIBLIOTECAS),
        ("UVAs", UVAS),
        ("Teatros", TEATROS),
    ]
    total = sum(len(g) for _, g in todos)
    print(f"Importando {total} equipamientos culturales públicos de Medellín...\n")

    for group_name, items in todos:
        print(f"--- {group_name} ({len(items)}) ---")
        for item in items:
            msg = upsert_equipamiento(item)
            print(msg)
        print()

    print("✅ Importación completa.")
    print("El auto-scraper procesará sus webs/Instagram en el próximo ciclo.")


if __name__ == "__main__":
    run()
