import { useParams, Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { useEffect, useState } from 'react'
import { commitEventosDescubiertos, discoverEventosAI, getZona, getZonaCulturaHoy, type Zona, type Evento, type Espacio } from '../lib/api'
import BuscarConAI from '../components/ui/BuscarConAI'
import SmartEventImage from '../components/ui/SmartEventImage'
import { getEventDateParts } from '../lib/datetime'

export default function ZonaDetalle() {
  const { slug } = useParams()
  const [zona, setZona] = useState<Zona | null>(null)
  const [eventos, setEventos] = useState<Evento[]>([])
  const [espacios, setEspacios] = useState<Espacio[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const reloadCultura = () => {
    if (!slug) return
    getZonaCulturaHoy(slug).then(c => {
      setEventos(c.eventos ?? [])
      setEspacios(c.espacios ?? [])
    }).catch(() => {})
  }

  useEffect(() => {
    const cargarZona = async () => {
      if (!slug) {
        setError('Zona no valida.')
        setLoading(false)
        return
      }

      try {
        const [data, cultura] = await Promise.all([
          getZona(slug),
          getZonaCulturaHoy(slug),
        ])
        setZona(data)
        setEventos(cultura.eventos ?? [])
        setEspacios(cultura.espacios ?? [])
      } catch {
        setError('No fue posible cargar la zona cultural.')
      } finally {
        setLoading(false)
      }
    }

    void cargarZona()
  }, [slug])

  return (
    <>
      <Helmet>
        <title>Zona {zona?.nombre ?? slug} - Cultura ETÉREA</title>
      </Helmet>

      <div className="max-w-7xl mx-auto px-6 py-12">
        {loading ? <p className="font-mono">Cargando zona...</p> : null}
        {error ? <p className="font-mono border-2 border-black p-4">{error}</p> : null}

        {zona && (
          <>
            <div className="mb-12">
              <div className="flex items-center gap-3 mb-4">
                <span className="w-3 h-3 bg-black" />
                <span className="text-[11px] font-mono font-bold uppercase tracking-[0.3em]">{zona.municipio}</span>
              </div>
              <h1 className="text-5xl md:text-6xl font-heading font-black uppercase tracking-tighter mb-4">
                {zona.nombre}
              </h1>
              {zona.vocacion && (
                <p className="text-lg font-mono opacity-80 max-w-xl">{zona.vocacion}</p>
              )}
              {zona.descripcion && (
                <p className="mt-4 font-mono text-sm leading-relaxed max-w-2xl opacity-70">{zona.descripcion}</p>
              )}
              <div className="mt-6">
                <BuscarConAI
                  label="Buscar eventos en esta zona"
                  onSearch={async () => {
                    const res = await discoverEventosAI({
                      municipio: zona.municipio,
                      texto: zona.nombre,
                      max_queries: 2,
                      max_results_per_query: 4,
                      auto_insert: true,
                    })
                    return {
                      message: res.message,
                      candidatos: res.result.candidatos ?? [],
                      variables: {
                        tipo_evento: 'cultural',
                        zona: zona.nombre,
                        fecha_actual: new Date().toISOString().slice(0, 10),
                      },
                    }
                  }}
                  onCommit={async candidatos => {
                    const saved = await commitEventosDescubiertos(candidatos)
                    return saved.message
                  }}
                  onComplete={reloadCultura}
                />
              </div>
            </div>

            {eventos.length > 0 && (
              <section className="mb-16">
                <div className="flex items-center gap-2 mb-6">
                  <span className="w-2 h-2 bg-black animate-pulse" />
                  <h2 className="text-2xl font-heading font-black uppercase tracking-wider">
                    Cultura en esta zona
                  </h2>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-0 border-2 border-black">
                  {eventos.map(ev => (
                    <Link
                      key={ev.id}
                      to={`/evento/${ev.slug}`}
                      className="group block border-b-2 border-r-2 border-black hover:bg-black hover:text-white transition-all duration-300 overflow-hidden"
                    >
                      {(() => {
                        const { diaCorto, hora } = getEventDateParts(ev)
                        const horaConfiable = ev.hora_confirmada === true && hora
                        const horaFallback = ev.fuente_url ? 'Horario en el enlace' : 'Horario por confirmar'
                        const horario = horaConfiable ? `${diaCorto} · ${hora}` : `${diaCorto} · ${horaFallback}`
                        return (
                          <>
                            {ev.imagen_url && (
                              <div className="h-40 overflow-hidden">
                                <SmartEventImage
                                  primaryUrl={ev.imagen_url}
                                  sourceUrl={ev.fuente_url}
                                  alt={ev.titulo}
                                  kind="card"
                                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                                  fallbackClassName="w-full h-full bg-black/10"
                                />
                              </div>
                            )}
                            <div className="p-4">
                              <div className="flex items-center gap-2 mb-2">
                                <span className="text-[9px] font-mono font-bold uppercase tracking-wider border border-current px-1.5 py-0.5">
                                  {ev.categoria_principal.replaceAll('_', ' ')}
                                </span>
                                {ev.es_gratuito && (
                                  <span className="text-[9px] font-mono font-bold uppercase tracking-wider opacity-60">Gratis</span>
                                )}
                              </div>
                              <h3 className="font-heading font-black text-sm uppercase tracking-wider mb-1 line-clamp-2">
                                {ev.titulo}
                              </h3>
                              <p className="text-[11px] font-mono opacity-60 group-hover:opacity-100">
                                {horario}
                              </p>
                              {ev.nombre_lugar && (
                                <p className="text-[10px] font-mono mt-1 opacity-50 group-hover:opacity-80">
                                  {ev.nombre_lugar}
                                </p>
                              )}
                            </div>
                          </>
                        )
                      })()}
                    </Link>
                  ))}
                </div>
              </section>
            )}

            {espacios.length > 0 && (
              <section>
                <div className="flex items-center gap-2 mb-6">
                  <span className="w-4 h-4 bg-black" />
                  <h2 className="text-2xl font-heading font-black uppercase tracking-wider">
                    Espacios activos
                  </h2>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-0 border-2 border-black">
                  {espacios.map(esp => (
                    <Link
                      key={esp.id}
                      to={`/espacio/${esp.slug}`}
                      className="group block p-5 border-b-2 border-r-2 border-black hover:bg-black hover:text-white transition-all duration-300"
                    >
                      <span className="text-[9px] font-mono font-bold uppercase tracking-wider border border-current px-1.5 py-0.5">
                        {esp.categoria_principal.replaceAll('_', ' ')}
                      </span>
                      <h3 className="font-heading font-black text-sm uppercase tracking-wider mt-2 mb-1">
                        {esp.nombre}
                      </h3>
                      <p className="text-[11px] font-mono opacity-60 group-hover:opacity-100">
                        {esp.barrio ?? esp.municipio}
                      </p>
                      {esp.descripcion_corta && (
                        <p className="text-[10px] font-mono mt-2 opacity-50 group-hover:opacity-80 line-clamp-2">
                          {esp.descripcion_corta}
                        </p>
                      )}
                    </Link>
                  ))}
                </div>
              </section>
            )}

            {eventos.length === 0 && espacios.length === 0 && !loading && (
              <div className="border-2 border-black p-8 text-center space-y-4">
                <p className="font-mono text-sm uppercase tracking-wider">
                  No hay eventos activos en esta zona por ahora.
                </p>
                <div className="flex justify-center">
                  <BuscarConAI
                    label="Buscar eventos con AI"
                    onSearch={async () => {
                      const res = await discoverEventosAI({
                        municipio: zona.municipio,
                        texto: zona.nombre,
                        max_queries: 2,
                        max_results_per_query: 5,
                        auto_insert: true,
                      })
                      return {
                        message: res.message,
                        candidatos: res.result.candidatos ?? [],
                        variables: {
                          tipo_evento: 'cultural',
                          zona: zona.nombre,
                          fecha_actual: new Date().toISOString().slice(0, 10),
                        },
                      }
                    }}
                    onCommit={async candidatos => {
                      const saved = await commitEventosDescubiertos(candidatos)
                      return saved.message
                    }}
                    onComplete={reloadCultura}
                  />
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </>
  )
}
