import { useParams, Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { useEffect, useState } from 'react'
import { commitEventosDescubiertos, discoverEventosAI, getEspacio, getEventosByEspacio, getEspacios, registrarInteraccion, type Espacio, type Evento } from '../lib/api'
import { useAuth } from '../lib/AuthContext'
import ReviewSection from '../components/ui/ReviewSection'
import { formatEventDate, getEventDateParts } from '../lib/datetime'
import BuscarConAI from '../components/ui/BuscarConAI'

export default function EspacioDetalle() {
  const { slug } = useParams()
  const { user } = useAuth()
  const [espacio, setEspacio] = useState<Espacio | null>(null)
  const [eventos, setEventos] = useState<Evento[]>([])
  const [cercanos, setCercanos] = useState<Espacio[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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

  return (
    <>
      <Helmet>
        <title>{espacio.nombre} - Cultura ETÉREA</title>
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
              <BuscarConAI
                label="Ayudanos a buscar eventos en este perfil o lugar"
                onSearch={async () => {
                  const res = await discoverEventosAI({
                    colectivo_slug: espacio.slug,
                    municipio: espacio.municipio,
                    categoria: espacio.categoria_principal,
                    texto: espacio.nombre,
                    max_queries: 2,
                    max_results_per_query: 4,
                    auto_insert: true,
                  })
                  return {
                    message: res.message,
                    candidatos: res.result.candidatos ?? [],
                    variables: {
                      tipo_evento: espacio.categoria_principal,
                      zona: espacio.municipio,
                      fecha_actual: new Date().toISOString().slice(0, 10),
                    },
                  }
                }}
                onCommit={async candidatos => {
                  const saved = await commitEventosDescubiertos(candidatos)
                  return saved.message
                }}
                onComplete={() => {
                  getEventosByEspacio(espacio.id).then(setEventos).catch(() => {})
                }}
              />
            </div>
            {eventos.length === 0 ? (
              <p className="font-mono text-sm">No hay eventos próximos programados en este espacio.</p>
            ) : (
              <div className="space-y-0 border-2 border-black">
                {eventos.map(ev => {
                  const { diaCorto, hora } = getEventDateParts(ev)
                  const enCurso = (ev as Evento & { _en_curso?: boolean })._en_curso
                  return (
                    <Link
                      key={ev.id}
                      to={`/evento/${ev.slug}`}
                      className="block border-b-2 border-black last:border-b-0 p-4 hover:bg-black hover:text-white transition-all duration-300"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          {enCurso && (
                            <span className="text-[9px] font-mono font-bold bg-red-600 text-white px-1.5 py-0.5 mr-2 uppercase">EN CURSO</span>
                          )}
                          <p className="font-heading font-bold uppercase tracking-wider text-sm">{ev.titulo}</p>
                          <p className="text-xs font-mono mt-1">
                            {diaCorto}
                            {hora ? ` · ${hora}` : ''}
                            {ev.fecha_fin && (
                              <> → {formatEventDate(ev.fecha_fin, { day: 'numeric', month: 'short' })}</>
                            )}
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