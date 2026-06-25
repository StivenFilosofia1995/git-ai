import asyncio
import json
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session
from app.models import EspacioCultural
from app.utils import normalizar_espacio_datos
from app.services import generate_embedding

async def seed_espacios():
    """Cargar datos base de espacios culturales."""
    data_path = Path(__file__).parent / "data" / "espacios_base.json"

    with open(data_path, 'r', encoding='utf-8') as f:
        espacios_data = json.load(f)

    async with async_session() as session:
        for espacio_data in espacios_data:
            # Normalizar datos
            normalizados = normalizar_espacio_datos(espacio_data)

            # Generar embedding para búsqueda semántica
            texto_para_embedding = f"{normalizados['nombre']} {normalizados.get('descripcion_corta', '')} {normalizados.get('enfoque_estrategico', '')}"
            embedding = await generate_embedding(texto_para_embedding)

            # Crear objeto EspacioCultural
            espacio = EspacioCultural(
                nombre=normalizados['nombre'],
                slug=normalizados['slug'],
                tipo=normalizados['tipo'],
                categorias=normalizados['categorias'],
                categoria_principal=normalizados['categoria_principal'],
                municipio=normalizados['municipio'],
                barrio=normalizados.get('barrio'),
                comuna=normalizados.get('comuna'),
                direccion=normalizados.get('direccion'),
                descripcion_corta=normalizados.get('descripcion_corta'),
                descripcion=normalizados.get('descripcion'),
                enfoque_estrategico=normalizados.get('enfoque_estrategico'),
                contexto_historico=normalizados.get('contexto_historico'),
                instagram_handle=normalizados.get('instagram_handle'),
                instagram_seguidores=normalizados.get('instagram_seguidores'),
                sitio_web=normalizados.get('sitio_web'),
                nivel_actividad=normalizados['nivel_actividad'],
                es_underground=normalizados['es_underground'],
                es_institucional=normalizados['es_institucional'],
                modelo_sostenibilidad=normalizados.get('modelo_sostenibilidad'),
                fuente_datos=normalizados['fuente_datos'],
                embedding=embedding
            )

            # Agregar coordenadas si existen
            if 'coordenadas' in normalizados:
                from geoalchemy2 import WKTElement
                coords = normalizados['coordenadas']
                espacio.coordenadas = WKTElement(f"POINT({coords['lng']} {coords['lat']})", srid=4326)

            # Insertar o actualizar
            await session.merge(espacio)

        await session.commit()
        print(f"Seeded {len(espacios_data)} espacios culturales")

if __name__ == "__main__":
    asyncio.run(seed_espacios())