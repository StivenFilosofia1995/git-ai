import { useParams, Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { getEvento, registrarInteraccion, type Evento } from '../lib/api'
import { useAuth } from '../lib/AuthContext'
import ReviewSection from '../components/ui/ReviewSection'
import { getEventDateParts } from '../lib/datetime'

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

  const { diaLargo: fechaStr, hora: horaStr } = getEventDateParts(evento)
  const horaConfiable = evento.hora_confirmada === true && horaStr
  const fuenteUrl = evento.fuente_url ?? null
  const fuenteUrlValue = fuenteUrl ?? ''
  const horaLabel = horaConfiable
    ? horaStr
    : 'Horario por confirmar'
  const mostrarHorarioEnlace = !horaConfiable && Boolean(fuenteUrl)
  const horaTextoCompartir = mostrarHorarioEnlace ? 'Horario en el enlace' : horaLabel
  const ubicacionLabel = [evento.nombre_lugar, evento.barrio, evento.municipio].filter(Boolean).join(', ')
  const mapsSearchTarget = ubicacionLabel || `${evento.titulo}, Medellin`
  const mapsUrl = evento.lat && evento.lng
    ? `https://www.google.com/maps?q=${evento.lat},${evento.lng}`
    : `https://www.google.com/maps/search/${encodeURIComponent(mapsSearchTarget)}`
  const preguntaEterea = encodeURIComponent(
    `Quiero que me cuentes mas detalles solo de este evento: "${evento.titulo}". No me listes otros eventos. Fecha: ${fechaStr} ${horaLabel}. Lugar: ${ubicacionLabel || 'Medellin'}.`
  )

  const canonicalUrl = `https://culturaetereamed.com/evento/${slug}`
  const ubicacionLine = ubicacionLabel ? `\n📍 ${ubicacionLabel}` : ''
  const fechaShareLine = horaConfiable ? `${fechaStr} · ${horaStr}` : `${fechaStr} · ${horaTextoCompartir}`
  let horaContenido: ReactNode
  if (mostrarHorarioEnlace) {
    horaContenido = (
      <a
        href={fuenteUrlValue}
        target="_blank"
        rel="noopener noreferrer"
        className="text-lg underline"
      >
        Horario en el enlace
      </a>
    )
  } else if (horaConfiable) {
    horaContenido = <p className="text-lg">{horaLabel}</p>
  } else {
    horaContenido = <p className="text-lg">Horario por confirmar</p>
  }
  const whatsappText = encodeURIComponent(
    `📅 *${evento.titulo}*\n🗓 ${fechaShareLine}${ubicacionLine}\n\n${canonicalUrl}`
  )
  const whatsappUrl = `https://wa.me/?text=${whatsappText}`
  const metaDescription =
    evento.descripcion
      ? evento.descripcion.slice(0, 155)
      : `${evento.categoria_principal?.replaceAll('_', ' ')} en ${evento.nombre_lugar || evento.municipio}. ${fechaStr} — ${horaLabel}.`
  const eventSchema = {
    '@context': 'https://schema.org',
    '@type': 'Event',
    name: evento.titulo,
    startDate: evento.fecha_inicio,
    ...(evento.fecha_fin && { endDate: evento.fecha_fin }),
    description: evento.descripcion ?? undefined,
    ...(evento.imagen_url && { image: evento.imagen_url }),
    location: {
      '@type': 'Place',
      name: evento.nombre_lugar ?? ubicacionLabel ?? 'Medellín',
      address: {
        '@type': 'PostalAddress',
        addressLocality: evento.municipio ?? 'Medellín',
        addressRegion: 'Antioquia',
        addressCountry: 'CO',
      },
    },
    organizer: { '@type': 'Organization', name: 'Cultura ETÉREA', url: 'https://culturaetereamed.com' },
    isAccessibleForFree: evento.es_gratuito ?? false,
    offers: {
      '@type': 'Offer',
      price: evento.es_gratuito ? '0' : evento.precio ?? '',
      priceCurrency: 'COP',
      availability: 'https://schema.org/InStock',
      url: canonicalUrl,
    },
  }

  return (
    <>
      <Helmet>
        <title>{evento.titulo} — Cultura ETÉREA</title>
        <meta name="description" content={metaDescription} />
        <link rel="canonical" href={canonicalUrl} />
        {/* Open Graph */}
        <meta property="og:type" content="event" />
        <meta property="og:title" content={`${evento.titulo} — Cultura ETÉREA`} />
        <meta property="og:description" content={metaDescription} />
        <meta property="og:url" content={canonicalUrl} />
        {evento.imagen_url && <meta property="og:image" content={evento.imagen_url} />}
        <meta property="og:locale" content="es_CO" />
        {/* Twitter */}
        <meta name="twitter:card" content={evento.imagen_url ? 'summary_large_image' : 'summary'} />
        <meta name="twitter:title" content={evento.titulo} />
        <meta name="twitter:description" content={metaDescription} />
        {evento.imagen_url && <meta name="twitter:image" content={evento.imagen_url} />}
        {/* JSON-LD Event */}
        <script type="application/ld+json">{JSON.stringify(eventSchema)}</script>
      </Helmet>

      <div className="max-w-3xl mx-auto px-4 py-8">
        <Link to="/agenda" className="text-sm font-mono font-bold uppercase tracking-wider mb-8 inline-block hover:underline">
          ← AGENDA
        </Link>

        <div className="space-y-8">
          {/* Header */}
          <div>
            <span className="inline-block px-3 py-1 text-xs font-mono font-bold uppercase tracking-wider border-2 border-black mb-4">
              {evento.categoria_principal?.replaceAll('_', ' ')}
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
                {horaContenido}
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
              <a
                href={whatsappUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 text-sm font-mono font-bold uppercase tracking-wider border-2 border-[#25D366] text-[#25D366] px-4 py-2 hover:bg-[#25D366] hover:text-white transition-all"
              >
                <svg viewBox="0 0 24 24" className="w-4 h-4 fill-current" aria-hidden="true">
                  <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
                </svg>
                Compartir
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
