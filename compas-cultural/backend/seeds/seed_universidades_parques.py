import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import supabase

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[\xc1\xe1]', 'a', text)
    text = re.sub(r'[\xc9\xe9]', 'e', text)
    text = re.sub(r'[\xcd\xed]', 'i', text)
    text = re.sub(r'[\xd3\xf3]', 'o', text)
    text = re.sub(r'[\xda\xfa]', 'u', text)
    text = re.sub(r'\xf1', 'n', text)
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')

UNIVERSIDADES_PARQUES_CULTURALES = [
    {
        'nombre': 'Universidad de Antioquia (Extension Cultural)',
        'tipo': 'universidad',
        'categoria_principal': 'taller',
        'instagram_handle': 'extensionculturaludea',
        'sitio_web': 'https://www.udea.edu.co/wps/portal/udea/web/inicio/cultura',
        'barrio': 'Sevilla',
        'municipio': 'medellin',
        'direccion': 'Calle 67 N 53 - 108'
    },
    {
        'nombre': 'Universidad Nacional sede Medellin (Cultura)',
        'tipo': 'universidad',
        'categoria_principal': 'taller',
        'instagram_handle': 'culturaunalmed',
        'sitio_web': 'https://bienestar.medellin.unal.edu.co/cultura/',
        'barrio': 'Volador',
        'municipio': 'medellin',
        'direccion': 'Calle 59A No 63-20'
    },
    {
        'nombre': 'Universidad EAFIT (Agenda Cultural)',
        'tipo': 'universidad',
        'categoria_principal': 'cine',
        'instagram_handle': 'eafit',
        'sitio_web': 'https://www.eafit.edu.co/cultura',
        'barrio': 'Aguacatala',
        'municipio': 'medellin',
        'direccion': 'Carrera 49 N 7 Sur - 50'
    },
    {
        'nombre': 'Universidad Pontificia Bolivariana (Cultura)',
        'tipo': 'universidad',
        'categoria_principal': 'taller',
        'instagram_handle': 'upbcolombia',
        'sitio_web': 'https://www.upb.edu.co/es/cultura',
        'barrio': 'Laureles',
        'municipio': 'medellin',
        'direccion': 'Circular 1.a 70-01'
    },
    {
        'nombre': 'Parque Explora',
        'tipo': 'parque_cultural',
        'categoria_principal': 'charla',
        'instagram_handle': 'parqueexplora',
        'sitio_web': 'https://www.parqueexplora.org/',
        'barrio': 'Sevilla',
        'municipio': 'medellin',
        'direccion': 'Carrera 53 73 - 75'
    },
    {
        'nombre': 'Planetario de Medellin',
        'tipo': 'parque_cultural',
        'categoria_principal': 'charla',
        'instagram_handle': 'planetariomed',
        'sitio_web': 'https://www.planetariomedellin.org/',
        'barrio': 'Sevilla',
        'municipio': 'medellin',
        'direccion': 'Cra 52 71-117'
    },
    {
        'nombre': 'Jardin Botanico de Medellin',
        'tipo': 'parque_cultural',
        'categoria_principal': 'festival',
        'instagram_handle': 'jardinbotanicodemedellin',
        'sitio_web': 'https://www.botanicomedellin.org/',
        'barrio': 'Sevilla',
        'municipio': 'medellin',
        'direccion': 'Calle 73 N 51D - 14'
    },
    {
        'nombre': 'Parque de la Conservacion (antiguo Zoologico)',
        'tipo': 'parque_cultural',
        'categoria_principal': 'taller',
        'instagram_handle': 'parquedelaconservacion',
        'sitio_web': 'https://parquedelaconservacion.com/',
        'barrio': 'Guayabal',
        'municipio': 'medellin',
        'direccion': 'Carrera 52 20-63'
    },
    {
        'nombre': 'Centro Cultural Moravia',
        'tipo': 'centro_cultural',
        'categoria_principal': 'danza',
        'instagram_handle': 'centroculturalmoravia',
        'sitio_web': 'https://www.medellin.gov.co/es/dependencias/secretaria-de-cultura-ciudadana/centro-de-desarrollo-cultural-de-moravia/',
        'barrio': 'Moravia',
        'municipio': 'medellin',
        'direccion': 'Calle 82A No. 52 - 25'
    },
    {
        'nombre': 'Museo Casa de la Memoria',
        'tipo': 'museo',
        'categoria_principal': 'charla',
        'instagram_handle': 'museocasadelamemoria',
        'sitio_web': 'https://www.museocasadelamemoria.gov.co/',
        'barrio': 'Boston',
        'municipio': 'medellin',
        'direccion': 'Calle 51 36-66'
    },
    {
        'nombre': 'Museo El Castillo',
        'tipo': 'museo',
        'categoria_principal': 'literatura',
        'instagram_handle': 'museoelcastillo',
        'sitio_web': 'https://www.museoelcastillo.org/',
        'barrio': 'El Poblado',
        'municipio': 'medellin',
        'direccion': 'Calle 9 Sur 32-269'
    },
    {
        'nombre': 'Museo del Agua EPM',
        'tipo': 'museo',
        'categoria_principal': 'charla',
        'instagram_handle': 'museodelaguaepm',
        'sitio_web': 'https://www.fundacionepm.org.co/micrositios/museo-del-agua-epm/',
        'barrio': 'Alpujarra',
        'municipio': 'medellin',
        'direccion': 'Cra 57 42-139'
    },
    {
        'nombre': 'Palacio de la Cultura Rafael Uribe Uribe',
        'tipo': 'centro_cultural',
        'categoria_principal': 'arte_contemporaneo',
        'instagram_handle': 'culturaantioquia',
        'sitio_web': 'https://culturantioquia.gov.co/',
        'barrio': 'La Candelaria',
        'municipio': 'medellin',
        'direccion': 'Carrera 51 52-03'
    },
    {
        'nombre': 'Centro Plazarte',
        'tipo': 'centro_cultural',
        'categoria_principal': 'arte_contemporaneo',
        'instagram_handle': 'plazarte',
        'sitio_web': 'https://www.instagram.com/plazarte/',
        'barrio': 'Prado',
        'municipio': 'medellin',
        'direccion': 'Cra 50 59-36'
    },
    {
        'nombre': 'Parque de los Deseos',
        'tipo': 'parque_cultural',
        'categoria_principal': 'cine',
        'instagram_handle': 'fundacionepm',
        'sitio_web': 'https://www.fundacionepm.org.co/micrositios/parque-de-los-deseos/',
        'barrio': 'Sevilla',
        'municipio': 'medellin',
        'direccion': 'Calle 71 52-30'
    },
    {
        'nombre': 'Parque Biblioteca Espana - Santo Domingo', # Actually being rebuilt but let's have it
        'tipo': 'biblioteca',
        'categoria_principal': 'literatura',
        'instagram_handle': 'bibliotecasmed',
        'sitio_web': 'https://www.bibliotecasmedellin.gov.co/',
        'barrio': 'Santo Domingo Savio',
        'municipio': 'medellin',
        'direccion': 'Carrera 33B 107A-101'
    }
]

def insert_lugar(record: dict) -> str:
    slug = slugify(record['nombre'])
    payload = {
        'slug': slug,
        'nombre': record['nombre'],
        'tipo': record.get('tipo', 'espacio_cultural'),
        'categoria_principal': record.get('categoria_principal', 'otro'),
        'municipio': record.get('municipio', 'medellin'),
        'barrio': record.get('barrio'),
        'direccion': record.get('direccion'),
        'sitio_web': record.get('sitio_web'),
        'instagram_handle': record.get('instagram_handle'),
        
        
    }
    
    try:
        supabase.table('lugares').upsert(payload, on_conflict='slug').execute()
        return f'  ? {record["nombre"]}'
    except Exception as e:
        return f'  ? {record["nombre"]}: {e}'

if __name__ == '__main__':
    print('Importando Universidades, Parques y Centros Culturales...')
    for r in UNIVERSIDADES_PARQUES_CULTURALES:
        print(insert_lugar(r))
    print('\n? Importacion completa.')
