import { useParams, Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { useEffect, useState } from 'react'
import { getEspacio, getEventosByEspacio, getEspacios, registrarInteraccion, scrapeLugar, type Espacio, type Evento } from '../lib/api'
import { useAuth } from '../lib/AuthContext'
import ReviewSection from '../components/ui/ReviewSection'

export default function EspacioDetalle() {
  const { slug } = useParams()
  const { user } = useAuth()
  const [espacio, setEspacio] = useState<Espacio | null>(null)
  const [eventos, setEventos] = useState<Evento[]>([])
  const [cercanos, setCercanos] = useState<Espacio[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [scrapingEventos, setScrapingEventos] = useState(false)
  const [scrapeMsg, setScrapeMsg] = useState<string | null>(null)

  useEffect(() => {
    const cargarEspacio = async () => {
      if (!slug) {
        setError('Espacio no valido.')
        setLoading(false)
        return
      }

      setLoading(true)
      setError(null)
      try {
        const data = await getEspacio(slug)
        setEspacio(data)
        if (user) {
          registrarInteraccion({ tipo: 'view_espacio', item_id: data.id, categoria: data.categoria_principal }, user.id)
        }
        // Load events for this space
        getEventosByEspacio(data.id).then(setEventos).catch(() => {})
        // Load nearby spaces (same municipio)
        getEspacios({ limit: 5, municipio: data.municipio })
          .then(list => setCercanos(list.filter(e => e.id !== data.id).slice(0, 4)))
          .catch(() => {})
      } catch {
        setError('No fue posible cargar este espacio.')
      } finally {
        setLoading(false)
      }
    }

    void cargarEspacio()
  }, [slug, user])

  if (loading) return <div className="p-8 font-mono">Cargando...</div>
  if (error) return <div className="p-8 font-mono border-2 border-black">{error}</div>
  if (!espacio) return <div className="p-8 font-mono">Espacio no encontrado</div>

  const canonicalUrl = `https://culturaetereamed.com/espacio/${slug}`
  const metaDescription =
    espacio.descripcion_corta
      ? espacio.descripcion_corta.slice(0, 155)
      : `${espacio.categoria_principal?.replaceAll('_', ' ')} en ${espacio.barrio ?? ''} ${espacio.municipio}. Descubrí este espacio cultural en Cultura ETÉREA.`
  const placeSchema = {
    '@context': 'https://schema.org',
    '@type': 'LocalBusiness',
    name: espacio.nombre,
    description: espacio.descripcion_corta ?? espacio.descripcion ?? undefined,
    url: canonicalUrl,
    address: {
      '@type': 'PostalAddress',
      addressLocality: espacio.municipio ?? 'Medellín',
      streetAddress: espacio.barrio ?? undefined,
      addressRegion: 'Antioquia',
      addressCountry: 'CO',
    },
  }

  return (
    <>
      <Helmet>
        <title>{espacio.nombre} — Cultura ETÉREA</title>
        <meta name="description" content={metaDescription} />
        <link rel="canonical" href={canonicalUrl} />
        {/* Open Graph */}
        <meta property="og:type" content="place" />
        <meta property="og:title" content={`${espacio.nombre} — Cultura ETÉREA`} />
        <meta property="og:description" content={metaDescription} />
        <meta property="og:url" content={canonicalUrl} />
        <meta property="og:locale" content="es_CO" />
        {/* Twitter */}
        <meta name="twitter:card" content="summary" />
        <meta name="twitter:title" content={espacio.nombre} />
        <meta name="twitter:description" content={metaDescription} />
        {/* JSON-LD Place */}
        <script type="application/ld+json">{JSON.stringify(placeSchema)}</script>
      </Helmet>

      <div className="max-w-4xl mx-auto px-4 py-8">
        <Link to="/" className="text-sm font-mono font-bold uppercase tracking-wider mb-8 inline-block hover:underline">
          ← VOLVER
        </Link>

        <div className="space-y-8">
          <div>
            <h1 className="text-4xl font-mono font-bold mb-2 uppercase">{espacio.nombre}</h1>
            <p className="text-lg font-mono">
              {espacio.categoria_principal} · {espacio.nivel_actividad} · {espacio.barrio ?? 'Sin barrio'}, {espacio.municipio}
            </p>
          </div>

          <div className="border-t-2 border-black pt-8">
            {espacio.descripcion_corta ? <p className="text-lg mb-6">{espacio.descripcion_corta}</p> : null}
            <p>{espacio.descripcion ?? 'Sin descripcion ampliada.'}</p>
          </div>

          <div className="border-t-2 border-black pt-8">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h3 className="font-mono font-bold mb-2 uppercase tracking-wider text-xs">CONTACTO</h3>
                {espacio.instagram_handle && (
                  <p>
                    <a
                      href={`https://instagram.com/${espacio.instagram_handle.replace(/^@/, '')}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-2 text-sm font-mono border-2 border-black px-3 py-1.5 hover:bg-black hover:text-white transition-all mb-2"
                    >
                      📸 @{espacio.instagram_handle.replace(/^@/, '')}
                    </a>
                  </p>
                )}
                {espacio.sitio_web && (
                  <p>
                    <a
                      href={espacio.sitio_web}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-2 text-sm font-mono border-2 border-black px-3 py-1.5 hover:bg-black hover:text-white transition-all"
                    >
                      🌐 {espacio.sitio_web.replace(/^https?:\/\//, '').replace(/\/$/, '')}
                    </a>
                  </p>
                )}
              </div>
              <div>
                <h3 className="font-mono font-bold mb-2 uppercase tracking-wider text-xs">UBICACIÓN</h3>
                {espacio.direccion && (
                  <p className="font-mono text-sm">{espacio.direccion}</p>
                )}
                {espacio.barrio && espacio.barrio !== 'Sin barrio' && (
                  <p className="font-mono text-sm">{espacio.barrio}</p>
                )}
                <p className="font-mono text-sm capitalize">{espacio.municipio}</p>
                <a
                  href={
                    espacio.lat && espacio.lng
                      ? `https://www.google.com/maps?q=${espacio.lat},${espacio.lng}`
                      : `https://www.google.com/maps/search/${encodeURIComponent(`${espacio.nombre}, ${espacio.municipio}, Colombia`)}`
                  }
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 text-sm font-mono border-2 border-black px-3 py-1.5 mt-2 hover:bg-black hover:text-white transition-all"
                >
                  📍 Ver en Google Maps
                </a>
              </div>
            </div>
          </div>

          <div className="border-t-2 border-black pt-8">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-mono font-bold uppercase tracking-wider text-xs">PRÓXIMOS EVENTOS</h3>
              <button
                onClick={async () => {
                  setScrapingEventos(true)
                  setScrapeMsg('Buscando eventos en redes y sitios web...')
                  try {
                    const res = await scrapeLugar(espacio.id)
                    setScrapeMsg(res.message)
                    // Re-fetch events immediately since scrape is now synchronous
                    getEventosByEspacio(espacio.id).then(setEventos).catch(() => {})
                  } catch {
                    setScrapeMsg('No se pudo iniciar la búsqueda. Intenta de nuevo.')
                  } finally {
                    setScrapingEventos(false)
                  }
                }}
                disabled={scrapingEventos}
                className="text-[10px] font-mono font-bold uppercase tracking-wider border-2 border-black px-3 py-1.5 hover:bg-black hover:text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {scrapingEventos
                  ? <><span className="w-2 h-2 border-2 border-current border-t-transparent rounded-full animate-spin inline-block" /> Buscando...</>
                  : <>🔍 Buscar eventos</>
                }
              </button>
            </div>
            {scrapeMsg && (
              <p className="text-xs font-mono text-neutral-500 mb-3 border border-neutral-300 px-3 py-2">{scrapeMsg}</p>
            )}
            {eventos.length === 0 ? (
              <div className="space-y-3">
                <p className="font-mono text-sm">No hay eventos próximos programados en este espacio.</p>
                {scrapeMsg && (espacio.instagram_handle || espacio.sitio_web) && (
                  <div className="border-2 border-black p-4 bg-neutral-50">
                    <p className="font-mono text-xs font-bold uppercase tracking-wider mb-3">CONSULTAR DIRECTAMENTE:</p>
                    <div className="flex flex-wrap gap-2">
                      {espacio.instagram_handle && (
                        <a
                          href={`https://instagram.com/${espacio.instagram_handle.replace(/^@/, '')}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-2 text-xs font-mono border-2 border-black px-3 py-1.5 hover:bg-black hover:text-white transition-all"
                        >
                          📸 Ver Instagram
                        </a>
                      )}
                      {espacio.sitio_web && (
                        <a
                          href={espacio.sitio_web}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-2 text-xs font-mono border-2 border-black px-3 py-1.5 hover:bg-black hover:text-white transition-all"
                        >
                          🌐 Ver sitio web
                        </a>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-0 border-2 border-black">
                {eventos.map(ev => {
                  const fecha = new Date(ev.fecha_inicio)
                  return (
                    <Link
                      key={ev.id}
                      to={`/evento/${ev.slug}`}
                      className="block border-b-2 border-black last:border-b-0 p-4 hover:bg-black hover:text-white transition-all duration-300"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="font-heading font-bold uppercase tracking-wider text-sm">{ev.titulo}</p>
                          <p className="text-xs font-mono mt-1">
                            {fecha.toLocaleDateString('es-CO', { weekday: 'short', day: 'numeric', month: 'short' })}
                            {' · '}
                            {fecha.toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' })}
                          </p>
                        </div>
                        {ev.es_gratuito && (
                          <span className="text-[10px] font-mono font-bold border-2 border-current px-2 py-0.5 uppercase">Gratis</span>
                        )}
                      </div>
                    </Link>
                  )
                })}
              </div>
            )}
          </div>

          <div className="border-t-2 border-black pt-8">
            <h3 className="font-mono font-bold mb-4 uppercase tracking-wider text-xs">ESPACIOS CERCANOS</h3>
            {cercanos.length === 0 ? (
              <p className="font-mono text-sm">No se encontraron espacios cercanos.</p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {cercanos.map(esp => (
                  <Link
                    key={esp.id}
                    to={`/espacio/${esp.slug}`}
                    className="block border-2 border-black p-4 hover:bg-black hover:text-white transition-all duration-300"
                  >
                    <p className="font-heading font-bold text-sm uppercase tracking-wider">{esp.nombre}</p>
                    <p className="text-xs font-mono mt-1">
                      {esp.categoria_principal?.replace(/_/g, ' ')} · {esp.barrio ?? esp.municipio}
                    </p>
                  </Link>
                ))}
              </div>
            )}
          </div>

          {/* Reviews */}
          <ReviewSection tipo="espacio" itemId={espacio.id} itemNombre={espacio.nombre} />
        </div>
      </div>
    </>
  )
}