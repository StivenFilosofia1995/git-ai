import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../lib/AuthContext'
import { obtenerRecomendaciones, getEventosFeed, type Evento } from '../../lib/api'

export default function RecomendacionesSection() {
  const { user } = useAuth()
  const [eventos, setEventos] = useState<Evento[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        if (user) {
          const recs = await obtenerRecomendaciones(user.id, 6)
          setEventos(recs)
        } else {
          // Show general diverse picks for anonymous users
          const feed = await getEventosFeed(6)
          setEventos(feed)
        }
      } catch {
        /* silent */
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [user])

  if (!loading && eventos.length === 0) return null

  return (
    <section className="py-16 border-t-2 border-black">
      <div className="flex items-end justify-between mb-8">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="w-2 h-2 bg-black animate-pulse" />
            <span className="text-[10px] font-mono font-bold uppercase tracking-[0.2em]">Para ti</span>
          </div>
          <h2 className="text-3xl md:text-4xl font-heading font-black uppercase tracking-tighter">
            {user ? 'Recomendado' : 'Explorá'}
          </h2>
          <p className="text-xs font-mono mt-1 uppercase tracking-wider opacity-60">
            {user ? 'Basado en tus gustos e interacciones' : 'Eventos diversos del Valle de Aburrá'}
          </p>
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="border-2 border-black p-5 animate-pulse">
              <div className="h-36 bg-black/10 mb-3" />
              <div className="h-4 bg-black/10 mb-2 w-2/3" />
              <div className="h-3 bg-black/5 w-1/2" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-0 border-2 border-black">
          {eventos.map(ev => (
            <Link
              key={ev.id}
              to={`/evento/${ev.slug}`}
              className="group block border-b-2 border-r-2 border-black hover:bg-black hover:text-white transition-all duration-300 overflow-hidden"
            >
              {ev.imagen_url && (
                <div className="h-36 overflow-hidden">
                  <img
                    src={ev.imagen_url}
                    alt={ev.titulo}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                  />
                </div>
              )}
              <div className="p-4">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-[9px] font-mono font-bold uppercase tracking-wider border border-current px-1.5 py-0.5">
                    {ev.categoria_principal.replaceAll('_', ' ')}
                  </span>
                  {ev.es_gratuito && (
                    <span className="text-[9px] font-mono font-bold uppercase tracking-wider opacity-60">
                      Gratis
                    </span>
                  )}
                </div>
                <h3 className="font-heading font-black text-sm uppercase tracking-wider mb-1 line-clamp-2">
                  {ev.titulo}
                </h3>
                <p className="text-[11px] font-mono opacity-60 group-hover:opacity-100">
                  {new Date(ev.fecha_inicio).toLocaleDateString('es-CO', {
                    weekday: 'short', day: 'numeric', month: 'short'
                  })}
                  {ev.nombre_lugar ? ` · ${ev.nombre_lugar}` : ''}
                </p>
              </div>
            </Link>
          ))}
        </div>
      )}
    </section>
  )
}
