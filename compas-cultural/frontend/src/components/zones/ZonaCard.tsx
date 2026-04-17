import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getZonaCulturaHoy, type Zona, type Evento } from '../../lib/api'

interface ZonaCardProps {
  zona: Zona
  index: number
}

export default function ZonaCard({ zona, index }: Readonly<ZonaCardProps>) {
  const [eventos, setEventos] = useState<Evento[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getZonaCulturaHoy(zona.slug)
      .then(data => setEventos(data.eventos?.slice(0, 2) ?? []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [zona.slug])

  // Tomar la primera imagen disponible de los eventos
  const imagenPrincipal = eventos.find(e => e.imagen_url)?.imagen_url

  return (
    <Link
      to={`/zona/${zona.slug}`}
      className="group relative block border-b-2 border-r-2 border-black hover:bg-black hover:text-white transition-all duration-300 overflow-hidden"
    >
      {/* Imagen de fondo si hay eventos con imagen */}
      {imagenPrincipal && (
        <div className="h-28 overflow-hidden relative">
          <img
            src={imagenPrincipal}
            alt={zona.nombre}
            className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-700 opacity-90 group-hover:opacity-40"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-white group-hover:from-black to-transparent" />
        </div>
      )}

      <div className="p-5">
        <div className="text-[10px] font-mono font-bold mb-2 tracking-wider opacity-40 group-hover:opacity-100">
          {String(index + 1).padStart(2, '0')}
        </div>
        <h3 className="font-heading font-black text-sm uppercase tracking-wider mb-1">
          {zona.nombre}
        </h3>
        <p className="text-xs font-mono leading-relaxed line-clamp-2 opacity-60 group-hover:opacity-100 mb-3">
          {zona.vocacion ?? zona.municipio}
        </p>

        {/* Mini preview de eventos hoy */}
        {!loading && eventos.length > 0 && (
          <div className="space-y-1.5 border-t border-current/20 pt-2 mt-2">
            <span className="text-[8px] font-mono font-bold uppercase tracking-[0.2em] opacity-50 group-hover:opacity-80 flex items-center gap-1">
              <span className="w-1 h-1 bg-current animate-pulse" />
              Hoy
            </span>
            {eventos.map(ev => (
              <div key={ev.id} className="flex items-center gap-2">
                {ev.imagen_url && (
                  <img src={ev.imagen_url} alt="" className="w-6 h-6 object-cover border border-current/20 shrink-0" />
                )}
                <span className="text-[10px] font-mono line-clamp-1 opacity-80 group-hover:opacity-100">
                  {ev.titulo}
                </span>
              </div>
            ))}
          </div>
        )}

        <div className="mt-3 text-[9px] font-mono font-bold tracking-[0.2em] uppercase opacity-40 group-hover:opacity-100">
          {zona.municipio}
        </div>
      </div>
    </Link>
  )
}
