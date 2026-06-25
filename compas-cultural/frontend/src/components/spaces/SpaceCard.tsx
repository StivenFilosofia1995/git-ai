import { Link } from 'react-router-dom'
import { type Espacio } from '../../lib/api'

interface SpaceCardProps {
  espacio: Espacio
}

export default function SpaceCard({ espacio }: Readonly<SpaceCardProps>) {
  return (
    <Link
      to={`/espacio/${espacio.slug}`}
      className="group block border-2 border-black p-5 hover:bg-black hover:text-white transition-all duration-300 hover-lift"
    >
      <div className="flex justify-between items-start mb-3">
        <span className="text-[10px] font-mono font-bold uppercase tracking-wider border-2 border-current px-2 py-0.5">
          {espacio.categoria_principal.replaceAll('_', ' ')}
        </span>
        <span className="text-[10px] font-mono font-bold uppercase tracking-wider">{espacio.nivel_actividad}</span>
      </div>

      <h3 className="font-heading font-black text-sm uppercase tracking-wider mb-2">{espacio.nombre}</h3>

      <p className="text-[11px] font-mono mb-2">
        {espacio.barrio ?? 'Sin barrio'} · {espacio.municipio}
      </p>

      {espacio.descripcion_corta && (
        <p className="text-[11px] font-mono mb-2 line-clamp-2 opacity-60 group-hover:opacity-100 transition-opacity">
          {espacio.descripcion_corta}
        </p>
      )}

      {espacio.instagram_handle && (
        <p className="text-[11px] font-mono opacity-60 group-hover:opacity-100">@{espacio.instagram_handle}</p>
      )}
    </Link>
  )
}