import { useParams, Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { useEffect, useState } from 'react'
import { getEvento, registrarInteraccion, type Evento } from '../lib/api'
import { useAuth } from '../lib/AuthContext'
import ReviewSection from '../components/ui/ReviewSection'

export default function EventoDetalle() {
  const { slug } = useParams()
  const { user } = useAuth()
  const [evento, setEvento] = useState<Evento | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!slug) {
      setError('Evento no válido.')
      setLoading(false)
      return
    }
    setLoading(true)
    getEvento(slug)
      .then(ev => {
        setEvento(ev)
        if (user) {
          registrarInteraccion({ tipo: 'view_evento', item_id: ev.id, categoria: ev.categoria_principal }, user.id)
        }
      })
      .catch(() => setError('No fue posible cargar este evento.'))
      .finally(() => setLoading(false))
  }, [slug, user])

  if (loading) return <div className="max-w-3xl mx-auto px-4 py-12 font-mono">Cargando...</div>
  if (error) return <div className="max-w-3xl mx-auto px-4 py-12 font-mono border-2 border-black p-4">{error}</div>
  if (!evento) return <div className="max-w-3xl mx-auto px-4 py-12 font-mono">Evento no encontrado</div>

  const fecha = new Date(evento.fecha_inicio)
  const fechaStr = fecha.toLocaleDateString('es-CO', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
  const horaStr = fecha.toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' })
  const ubicacionLabel = [evento.nombre_lugar, evento.barrio, evento.municipio].filter(Boolean).join(', ')
  const mapsUrl = evento.lat && evento.lng
    ? `https://www.google.com/maps?q=${evento.lat},${evento.lng}`
    : `https://www.google.com/maps/search/${encodeURIComponent(ubicacionLabel || `${evento.titulo}, Medellin`)}`
  const preguntaEterea = encodeURIComponent(
    `Recomiendame mas detalles de este evento: ${evento.titulo}. Fecha: ${fechaStr} ${horaStr}. Lugar: ${ubicacionLabel || 'Medellin'}.`
  )

  return (
    <>
      <Helmet>
        <title>{evento.titulo} — Cultura ETÉREA</title>
      </Helmet>

      <div className="max-w-3xl mx-auto px-4 py-8">
        <Link to="/agenda" className="text-sm font-mono font-bold uppercase tracking-wider mb-8 inline-block hover:underline">
          ← AGENDA
        </Link>

        <div className="space-y-8">
          {/* Header */}
          <div>
            <span className="inline-block px-3 py-1 text-xs font-mono font-bold uppercase tracking-wider border-2 border-black mb-4">
              {evento.categoria_principal?.replace(/_/g, ' ')}
            </span>
            <h1 className="text-3xl md:text-4xl font-heading font-black tracking-tight mb-3 uppercase">
              {evento.titulo}
            </h1>
          </div>

          {/* Image */}
          {evento.imagen_url && (
            <div className="overflow-hidden border-2 border-black">
              <img
                src={evento.imagen_url}
                alt={evento.titulo}
                className="w-full h-64 md:h-80 object-cover"
              />
            </div>
          )}

          {/* Info grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 border-t-2 border-black pt-8">
            <div className="space-y-4">
              <div>
                <h3 className="font-mono font-bold text-xs mb-1 uppercase tracking-wider">FECHA</h3>
                <p className="text-lg capitalize">{fechaStr}</p>
              </div>
              <div>
                <h3 className="font-mono font-bold text-xs mb-1 uppercase tracking-wider">HORA</h3>
                <p className="text-lg">{horaStr}</p>
              </div>
              <div>
                <h3 className="font-mono font-bold text-xs mb-1 uppercase tracking-wider">PRECIO</h3>
                <p className="text-lg">
                  {evento.es_gratuito ? (
                    <span className="font-bold border-2 border-black px-2 py-0.5 text-sm">ENTRADA LIBRE</span>
                  ) : (
                    evento.precio ?? 'No especificado'
                  )}
                </p>
              </div>
            </div>
            <div className="space-y-4">
              {evento.nombre_lugar && (
                <div>
                  <h3 className="font-mono font-bold text-xs mb-1 uppercase tracking-wider">LUGAR</h3>
                  <p className="text-lg">{evento.nombre_lugar}</p>
                </div>
              )}
              {(evento.barrio || evento.municipio) && (
                <div>
                  <h3 className="font-mono font-bold text-xs mb-1 uppercase tracking-wider">UBICACIÓN</h3>
                  <p className="text-lg">{[evento.barrio, evento.municipio].filter(Boolean).join(', ')}</p>
                </div>
              )}
            </div>
          </div>

          <div className="border-t-2 border-black pt-6">
            <h3 className="font-mono font-bold text-xs mb-3 uppercase tracking-wider">ACCIONES RÁPIDAS</h3>
            <div className="flex flex-wrap gap-3">
              <Link
                to={`/chat?q=${preguntaEterea}`}
                className="inline-flex items-center gap-2 text-sm font-mono font-bold uppercase tracking-wider border-2 border-black px-4 py-2 hover:bg-black hover:text-white transition-all"
              >
                🤖 Habla con ETÉREA sobre este evento
              </Link>
              <a
                href={mapsUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 text-sm font-mono font-bold uppercase tracking-wider border-2 border-black px-4 py-2 hover:bg-black hover:text-white transition-all"
              >
                📍 Ver ubicación
              </a>
              {evento.fuente_url && (
                <a
                  href={evento.fuente_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 text-sm font-mono font-bold uppercase tracking-wider border-2 border-black px-4 py-2 hover:bg-black hover:text-white transition-all"
                >
                  ℹ Más información
                </a>
              )}
            </div>
          </div>

          {/* Source links */}
          {evento.fuente_url && (
            <div className="border-t-2 border-black pt-6">
              <h3 className="font-mono font-bold text-xs mb-3 uppercase tracking-wider">FUENTE</h3>
              <a
                href={evento.fuente_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 text-sm font-mono font-bold border-2 border-black px-4 py-2 hover:bg-black hover:text-white transition-all"
              >
                {evento.fuente?.includes('instagram') ? '📸 Ver en Instagram' : '🌐 Ver fuente original'}
              </a>
            </div>
          )}

          {/* Description */}
          {evento.descripcion && (
            <div className="border-t-2 border-black pt-8">
              <h3 className="font-mono font-bold text-xs mb-3 uppercase tracking-wider">DESCRIPCIÓN</h3>
              <p className="leading-relaxed whitespace-pre-line">{evento.descripcion}</p>
            </div>
          )}

          {/* Reviews */}
          <ReviewSection tipo="evento" itemId={evento.id} itemNombre={evento.titulo} />
        </div>
      </div>
    </>
  )
}
