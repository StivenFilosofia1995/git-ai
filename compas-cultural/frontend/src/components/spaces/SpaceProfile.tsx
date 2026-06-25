interface Espacio {
  nombre: string
  categoria_principal: string
  barrio: string
  municipio: string
  descripcion_corta?: string
  descripcion?: string
  instagram_handle?: string
  sitio_web?: string
  nivel_actividad: string
}

interface SpaceProfileProps {
  espacio: Espacio
}

export default function SpaceProfile({ espacio }: SpaceProfileProps) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-mono font-bold mb-2">{espacio.nombre}</h1>
        <p className="text-lg">
          {espacio.categoria_principal} · {espacio.nivel_actividad} · {espacio.barrio}, {espacio.municipio}
        </p>
      </div>

      {espacio.descripcion_corta && (
        <p className="text-lg">{espacio.descripcion_corta}</p>
      )}

      {espacio.descripcion && (
        <div className="border-t-2 border-black pt-6">
          <p>{espacio.descripcion}</p>
        </div>
      )}

      <div className="border-t-2 border-black pt-6">
        <h3 className="font-mono font-bold mb-4">CONTACTO</h3>
        <div className="space-y-2">
          {espacio.instagram_handle && (
            <p>Instagram: @{espacio.instagram_handle}</p>
          )}
          {espacio.sitio_web && (
            <a href={espacio.sitio_web} className="underline" target="_blank" rel="noopener noreferrer">
              Sitio web
            </a>
          )}
        </div>
      </div>
    </div>
  )
}