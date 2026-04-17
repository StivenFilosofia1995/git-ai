import { Link } from 'react-router-dom'
import { type Evento } from '../../lib/api'

interface EventCardProps {
  evento: Evento
}

export default function EventCard({ evento }: Readonly<EventCardProps>) {
  const fecha = new Date(evento.fecha_inicio)
  const dia = fecha.toLocaleDateString('es-CO', { weekday: 'short', day: 'numeric', month: 'short' })
  const hora = fecha.toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' })
  const cat = evento.categoria_principal

  return (
    <Link
      to={`/evento/${evento.slug}`}
      className="group block bg-white border-2 border-black hover:bg-black hover:text-white transition-all duration-300 overflow-hidden hover-lift"
    >
      {evento.imagen_url && (
        <div className="aspect-[16/9] overflow-hidden border-b-2 border-black">
          <img
            src={evento.imagen_url}
            alt={evento.titulo}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500 group-hover:opacity-80"
            loading="lazy"
          />
        </div>
      )}

      <div className="p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] font-mono font-bold uppercase tracking-wider border-2 border-current px-2 py-0.5">
            {cat.replaceAll('_', ' ')}
          </span>
          <span className="text-[10px] font-mono font-bold">{dia} &middot; {hora}</span>
        </div>

        <h3 className="font-heading font-black text-sm leading-snug mb-2 uppercase tracking-wide">
          {evento.titulo}
        </h3>

        <div className="flex items-center gap-1.5 text-[11px] font-mono">
          <span className="w-1.5 h-1.5 bg-current" />
          <span>{evento.nombre_lugar ?? evento.barrio ?? 'Medell&iacute;n'}</span>
          {evento.barrio && evento.nombre_lugar && (
            <span className="opacity-50">&middot; {evento.barrio}</span>
          )}
        </div>

        {evento.es_gratuito && (
          <span className="inline-block mt-2 text-[10px] font-mono font-bold uppercase tracking-wider border-2 border-current px-2 py-0.5">
            Gratis
          </span>
        )}
      </div>
    </Link>
  )
}
