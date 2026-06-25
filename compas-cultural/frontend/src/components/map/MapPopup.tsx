import { Link } from 'react-router-dom'

interface MapPopupProps {
  nombre: string
  categoria: string
  barrio: string
  instagram?: string
  sitioWeb?: string
  slug: string
}

export default function MapPopup({ nombre, categoria, barrio, instagram, sitioWeb, slug }: Readonly<MapPopupProps>) {
  return (
    <div className="p-4 max-w-sm">
      <h3 className="font-mono font-bold text-sm mb-1">{nombre}</h3>
      <p className="text-xs font-mono mb-2">{categoria} · {barrio}</p>

      <div className="space-y-1 text-xs">
        {instagram && (
          <p>@{instagram}</p>
        )}
        {sitioWeb && (
          <a href={sitioWeb} className="underline block" target="_blank" rel="noopener noreferrer">
            Sitio web
          </a>
        )}
      </div>

      <Link
        to={`/espacio/${slug}`}
        className="inline-block mt-3 text-xs font-mono uppercase underline"
      >
        Ver perfil
      </Link>
    </div>
  )
}