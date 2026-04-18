import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getEventosHoy, getEventos, type Evento } from '../../lib/api'

export default function EventosHoySection() {
  const [eventos, setEventos] = useState<Evento[]>([])
  const [loading, setLoading] = useState(true)
  const [label, setLabel] = useState<'HOY' | 'ESTA SEMANA'>('HOY')

  useEffect(() => {
    const load = async () => {
      try {
        const hoy = await getEventosHoy()
        if (hoy.length > 0) {
          setEventos(hoy.slice(0, 8))
          setLabel('HOY')
        } else {
          const proximos = await getEventos({ limit: 8 })
          setEventos(proximos)
          setLabel('ESTA SEMANA')
        }
      } catch {
        /* silent */
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [])

  if (loading) {
    return (
      <div className="py-20 border-t-2 border-black">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-0 border-2 border-black">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="aspect-[3/4] bg-white border-r-2 border-black animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  if (eventos.length === 0) return null

  return (
    <section className="py-20 border-t-2 border-black">
      <div className="flex items-end justify-between mb-10">
        <div>
          <div className="flex items-center gap-3 mb-3">
            <span className="w-3 h-3 bg-black animate-pulse" />
            <span className="text-[10px] font-mono font-bold tracking-[0.3em] uppercase">{label}</span>
          </div>
          <h2 className="text-4xl md:text-5xl font-heading font-black uppercase tracking-tighter">
            {label === 'HOY' ? '\u00bfQu\u00e9 hay hoy?' : 'Pr\u00f3ximos'}
          </h2>
        </div>
        <Link
          to="/agenda"
          className="text-[11px] font-mono font-bold uppercase tracking-wider text-black hover:underline underline-offset-4"
        >
          Ver todo &rarr;
        </Link>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-0 border-2 border-black stagger">
        {eventos.map((evento) => (
          <EventoHoyCard key={evento.id} evento={evento} />
        ))}
      </div>
    </section>
  )
}

function EventoHoyCard({ evento }: Readonly<{ evento: Evento }>) {
  const fecha = new Date(evento.fecha_inicio)
  const hora = fecha.toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' })
  const dia = fecha.toLocaleDateString('es-CO', { weekday: 'short', day: 'numeric', month: 'short' })
  const cat = evento.categoria_principal

  return (
    <Link
      to={`/evento/${evento.slug}`}
      className="group relative flex flex-col justify-end aspect-[3/4] border-r-2 border-b-2 border-black overflow-hidden transition-all duration-500"
    >
      {evento.imagen_url ? (
        <>
          <img
            src={evento.imagen_url}
            alt={evento.titulo}
            className="absolute inset-0 w-full h-full object-cover group-hover:scale-110 group-hover:opacity-60 transition-all duration-700"
            loading="lazy"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/40 to-transparent" />
          <div className="relative p-5 text-white">
            <div className="flex items-center gap-2 mb-3">
              <span className="w-2 h-2 bg-white" />
              <span className="text-[10px] font-mono font-bold tracking-wider uppercase">{dia} · {hora}</span>
            </div>
            <h3 className="font-heading font-black text-sm uppercase tracking-wider mb-2 line-clamp-2 leading-snug">
              {evento.titulo}
            </h3>
            <div className="flex items-center gap-1.5 text-[10px] font-mono opacity-70">
              <span className="w-1.5 h-1.5 bg-white" />
              <span>{evento.nombre_lugar ?? 'Medellín'}</span>
            </div>
            {evento.es_gratuito && (
              <span className="inline-block mt-3 text-[9px] font-mono font-bold uppercase tracking-wider border border-white px-2 py-0.5">
                Gratis
              </span>
            )}
          </div>
        </>
      ) : (
        <div className="absolute inset-0 flex flex-col justify-end p-5 bg-white group-hover:bg-black group-hover:text-white transition-all duration-300">
          <div className="flex items-center gap-2 mb-3">
            <span className="w-2 h-2 bg-current" />
            <span className="text-[10px] font-mono font-bold tracking-wider uppercase">{dia} · {hora}</span>
          </div>
          <span className="text-[10px] font-mono font-bold uppercase tracking-wider border-2 border-current px-2 py-0.5 inline-block mb-3">
            {cat.replaceAll('_', ' ')}
          </span>
          <h3 className="font-heading font-black text-sm uppercase tracking-wider mb-2 line-clamp-2 leading-snug">
            {evento.titulo}
          </h3>
          <div className="flex items-center gap-1.5 text-[10px] font-mono opacity-60 group-hover:opacity-100">
            <span className="w-1.5 h-1.5 bg-current" />
            <span>{evento.nombre_lugar ?? 'Medellín'}</span>
          </div>
          {evento.es_gratuito && (
            <span className="inline-block mt-3 text-[9px] font-mono font-bold uppercase tracking-wider border-2 border-current px-2 py-0.5">
              Gratis
            </span>
          )}
        </div>
      )}
    </Link>
  )
}
