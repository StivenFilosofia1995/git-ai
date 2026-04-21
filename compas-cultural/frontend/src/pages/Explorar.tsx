import { Helmet } from 'react-helmet-async'
import { useEffect, useState, useMemo } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import SearchResults from '../components/search/SearchResults'
import EventCard from '../components/agenda/EventCard'
import { buscar, getEspacios, getEventos, getEventosHoy, getZonas, enviarMensajeChat, type Espacio, type Evento, type Zona, type ResultadoBusqueda, type ChatMessage } from '../lib/api'

const CAT_TABS = [
  { value: '', label: 'Todo' },
  { value: 'teatro', label: 'Teatro' },
  { value: 'rock', label: 'Rock / Metal' },
  { value: 'hip_hop', label: 'Hip-Hop' },
  { value: 'jazz', label: 'Jazz' },
  { value: 'electronica', label: 'Electrónica' },
  { value: 'galeria', label: 'Galerías' },
  { value: 'arte_contemporaneo', label: 'Arte Contemporáneo' },
  { value: 'libreria', label: 'Librerías' },
  { value: 'danza', label: 'Danza' },
  { value: 'musica_en_vivo', label: 'Música' },
  { value: 'poesia', label: 'Poesía' },
  { value: 'cine', label: 'Cine' },
  { value: 'filosofia', label: 'Filosofía' },
  { value: 'festival', label: 'Festivales' },
  { value: 'fotografia', label: 'Fotografía' },
  { value: 'muralismo', label: 'Muralismo' },
  { value: 'taller', label: 'Talleres' },
  { value: 'conferencia', label: 'Conferencias' },
]

type ViewMode = 'todo' | 'agenda' | 'espacios'

export default function Explorar() {
  const [searchParams] = useSearchParams()
  const query = searchParams.get('q')?.trim() ?? ''

  const [loading, setLoading] = useState(true)
  const [resultados, setResultados] = useState<ResultadoBusqueda[]>([])
  const [espacios, setEspacios] = useState<Espacio[]>([])
  const [eventos, setEventos] = useState<Evento[]>([])
  const [eventosHoy, setEventosHoy] = useState<Evento[]>([])
  const [zonas, setZonas] = useState<Zona[]>([])
  const [catFilter, setCatFilter] = useState('')
  const [muniFilter, setMuniFilter] = useState('')
  const [tipoFilter, setTipoFilter] = useState('')
  const [textFilter, setTextFilter] = useState('')
  const [viewMode, setViewMode] = useState<ViewMode>('todo')
  const [error, setError] = useState<string | null>(null)
  const [aiQuery, setAiQuery] = useState('')
  const [aiLoading, setAiLoading] = useState(false)
  const [aiResponse, setAiResponse] = useState<string | null>(null)

  useEffect(() => {
    const cargar = async () => {
      setLoading(true)
      setError(null)
      try {
        if (query) {
          const response = await buscar(query)
          setResultados(response.resultados)
        } else {
          const [esp, ev, hoy, z] = await Promise.all([
            getEspacios({ limit: 500 }),
            getEventos({ limit: 200 }),
            getEventosHoy(),
            getZonas(),
          ])
          setEspacios(esp)
          setEventos(ev)
          setEventosHoy(hoy)
          setZonas(z)
        }
      } catch {
        setError('No fue posible cargar los datos.')
      } finally {
        setLoading(false)
      }
    }
    void cargar()
  }, [query])

  const filteredEventos = useMemo(() => {
    let result = eventos
    if (catFilter) result = result.filter(e => e.categoria_principal === catFilter || e.categorias?.includes(catFilter))
    if (muniFilter) result = result.filter(e => e.municipio?.toLowerCase().includes(muniFilter.toLowerCase()))
    if (textFilter.trim()) {
      const q = textFilter.trim().toLowerCase()
      result = result.filter(e =>
        e.titulo?.toLowerCase().includes(q) ||
        e.nombre_lugar?.toLowerCase().includes(q) ||
        e.barrio?.toLowerCase().includes(q) ||
        e.municipio?.toLowerCase().includes(q) ||
        e.categoria_principal?.toLowerCase().includes(q)
      )
    }
    return result
  }, [eventos, catFilter, muniFilter, textFilter])

  const filteredEspacios = useMemo(() => {
    let result = espacios
    if (catFilter) result = result.filter(e => e.categoria_principal === catFilter || e.categorias?.includes(catFilter))
    if (muniFilter) result = result.filter(e => e.municipio?.toLowerCase().includes(muniFilter.toLowerCase()))
    if (tipoFilter) result = result.filter(e => e.tipo === tipoFilter)
    if (textFilter.trim()) {
      const q = textFilter.trim().toLowerCase()
      result = result.filter(e =>
        e.nombre?.toLowerCase().includes(q) ||
        e.descripcion_corta?.toLowerCase().includes(q) ||
        e.barrio?.toLowerCase().includes(q) ||
        e.municipio?.toLowerCase().includes(q) ||
        e.categoria_principal?.toLowerCase().includes(q) ||
        e.instagram_handle?.toLowerCase().includes(q)
      )
    }
    return result
  }, [espacios, catFilter, muniFilter, tipoFilter, textFilter])

  const filteredHoy = useMemo(() => {
    let result = eventosHoy
    if (catFilter) result = result.filter(e => e.categoria_principal === catFilter || e.categorias?.includes(catFilter))
    if (muniFilter) result = result.filter(e => e.municipio?.toLowerCase().includes(muniFilter.toLowerCase()))
    if (textFilter.trim()) {
      const q = textFilter.trim().toLowerCase()
      result = result.filter(e =>
        e.titulo?.toLowerCase().includes(q) ||
        e.nombre_lugar?.toLowerCase().includes(q) ||
        e.barrio?.toLowerCase().includes(q)
      )
    }
    return result
  }, [eventosHoy, catFilter, muniFilter, textFilter])

  const municipios = useMemo(() => {
    const set = new Set<string>()
    espacios.forEach(e => { if (e.municipio) set.add(e.municipio) })
    eventos.forEach(e => { if (e.municipio) set.add(e.municipio) })
    return Array.from(set).sort((a, b) => a.localeCompare(b))
  }, [espacios, eventos])

  // Group spaces by tipo for the "Red Cultural" section
  const TIPO_LABELS: Record<string, { label: string; icon: string }> = {
    colectivo: { label: 'Colectivos', icon: '◆' },
    espacio_fisico: { label: 'Espacios Físicos', icon: '■' },
    festival: { label: 'Festivales', icon: '★' },
    editorial: { label: 'Editoriales', icon: '◈' },
    plataforma_digital: { label: 'Plataformas Digitales', icon: '◎' },
    red_articuladora: { label: 'Redes Articuladoras', icon: '◇' },
    sello_discografico: { label: 'Sellos Discográficos', icon: '♫' },
    programa_institucional: { label: 'Programas Institucionales', icon: '▣' },
    publicacion: { label: 'Publicaciones', icon: '▤' },
  }

  const espaciosByTipo = useMemo(() => {
    const groups: Record<string, Espacio[]> = {}
    filteredEspacios.forEach(e => {
      const t = e.tipo || 'espacio_fisico'
      if (!groups[t]) groups[t] = []
      groups[t].push(e)
    })
    return groups
  }, [filteredEspacios])

  if (query) {
    return (
      <>
        <Helmet><title>Buscar: {query} — Cultura ETÉREA</title></Helmet>
        <div className="max-w-7xl mx-auto px-4 py-8">
          <h1 className="text-4xl font-mono font-bold mb-4">EXPLORAR</h1>
          <p className="font-mono text-sm mb-6 uppercase tracking-wider">
            Resultados para: <span className="font-bold">{query}</span>
          </p>
          <SearchResults resultados={resultados} loading={loading} />
        </div>
      </>
    )
  }

  return (
    <>
      <Helmet>
        <title>Explorar — Cultura ETÉREA</title>
      </Helmet>

      {/* HERO */}
      <section className="bg-white border-b-2 border-black">
        <div className="max-w-7xl mx-auto px-6 py-12 lg:py-16">
          <div className="flex items-start justify-between gap-8 flex-wrap">
            <div>
              <div className="flex items-center gap-3 mb-4">
                <span className="w-3 h-3 bg-black animate-pulse" />
                <span className="text-[11px] tracking-[0.3em] uppercase font-mono font-bold">
                  Agenda underground + oficial · Valle de Aburrá
                </span>
              </div>
              <h1 className="text-4xl md:text-6xl font-heading font-black tracking-tighter uppercase leading-[0.9] mb-4">
                Explorar
              </h1>
              <p className="text-sm font-mono leading-relaxed max-w-lg">
                Toda la cultura viva del Valle de Aburrá. Eventos, espacios, colectivos y agenda alternativa — actualizado cada 6 horas desde Instagram, webs y medios independientes.
              </p>
              {/* Text search */}
              <div className="mt-4 max-w-md">
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm">🔍</span>
                  <input
                    type="text"
                    value={textFilter}
                    onChange={e => setTextFilter(e.target.value)}
                    placeholder="Filtrar por nombre, lugar, barrio..."
                    className="w-full pl-9 pr-4 py-2.5 text-xs font-mono border-2 border-black focus:outline-none focus:ring-0 placeholder:text-neutral-400"
                  />
                  {textFilter && (
                    <button
                      onClick={() => setTextFilter('')}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-mono font-bold hover:opacity-70"
                    >
                      ✕
                    </button>
                  )}
                </div>
              </div>
              <form
                className="mt-3 flex gap-0 max-w-md"
                onSubmit={async (e) => {
                  e.preventDefault()
                  if (!aiQuery.trim() || aiLoading) return
                  setAiLoading(true)
                  setAiResponse(null)
                  try {
                    const historial: ChatMessage[] = []
                    const res = await enviarMensajeChat(aiQuery, historial)
                    setAiResponse(res.respuesta)
                  } catch {
                    setAiResponse('No pude consultar en este momento. Intentá de nuevo.')
                  } finally {
                    setAiLoading(false)
                  }
                }}
              >
                <input
                  type="text"
                  value={aiQuery}
                  onChange={e => setAiQuery(e.target.value)}
                  placeholder="Preguntale a ETÉREA... ¿qué hay hoy de jazz?"
                  className="flex-1 px-3 py-2 text-xs font-mono border-2 border-black border-r-0 focus:outline-none placeholder:text-neutral-400"
                />
                <button
                  type="submit"
                  disabled={aiLoading || !aiQuery.trim()}
                  className="text-[10px] font-mono font-bold uppercase tracking-wider border-2 border-black px-3 py-2 bg-black text-white hover:bg-neutral-800 transition-all disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap flex items-center gap-1.5"
                >
                  {aiLoading ? (
                    <><span className="w-2 h-2 border-2 border-white border-t-transparent rounded-full animate-spin inline-block" /> Buscando...</>
                  ) : '🔍 Preguntar'}
                </button>
              </form>
              {aiResponse && (
                <div className="mt-2 max-w-md text-xs font-mono leading-relaxed border border-black/20 px-3 py-2.5 bg-neutral-50 whitespace-pre-wrap">
                  {aiResponse}
                </div>
              )}
            </div>
            <div className="flex gap-6 text-center flex-wrap">
              <div>
                <div className="text-3xl font-heading font-black">{eventos.length}</div>
                <div className="text-[9px] font-mono font-bold tracking-[0.2em]">EVENTOS</div>
              </div>
              <div>
                <div className="text-3xl font-heading font-black">{espacios.length}</div>
                <div className="text-[9px] font-mono font-bold tracking-[0.2em]">ESPACIOS</div>
              </div>
              <div>
                <div className="text-3xl font-heading font-black">{zonas.length}</div>
                <div className="text-[9px] font-mono font-bold tracking-[0.2em]">ZONAS</div>
              </div>
              <div>
                <div className="text-3xl font-heading font-black">{Object.keys(espaciosByTipo).length}</div>
                <div className="text-[9px] font-mono font-bold tracking-[0.2em]">TIPOS</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* FILTERS BAR */}
      <div className="border-b-2 border-black bg-white sticky top-[60px] z-20">
        <div className="max-w-7xl mx-auto px-6 py-3">
          {/* View mode */}
          <div className="flex items-center gap-0 mb-3">
            {(['todo', 'agenda', 'espacios'] as ViewMode[]).map(mode => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`px-4 py-1.5 text-[10px] font-mono font-bold uppercase tracking-wider border-2 border-black -ml-[2px] first:ml-0 transition-all ${
                  viewMode === mode ? 'bg-black text-white' : 'hover:bg-black/5'
                }`}
              >
                {mode === 'todo' ? `Todo (${filteredEventos.length + filteredEspacios.length})` :
                 mode === 'agenda' ? `Agenda (${filteredEventos.length})` :
                 `Espacios (${filteredEspacios.length})`}
              </button>
            ))}
          </div>

          {/* Municipio + Tipo filters */}
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <select
              value={muniFilter}
              onChange={(e) => setMuniFilter(e.target.value)}
              className="text-[10px] font-mono font-bold uppercase tracking-wider border-2 border-black px-2 py-1 bg-white"
            >
              <option value="">Todo el Valle de Aburrá</option>
              {municipios.map(m => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
            <select
              value={tipoFilter}
              onChange={(e) => setTipoFilter(e.target.value)}
              className="text-[10px] font-mono font-bold uppercase tracking-wider border-2 border-black px-2 py-1 bg-white"
            >
              <option value="">Todos los tipos</option>
              <option value="espacio_fisico">Espacios físicos</option>
              <option value="colectivo">Colectivos</option>
              <option value="festival">Festivales</option>
              <option value="editorial">Editoriales</option>
              <option value="red_articuladora">Redes articuladoras</option>
              <option value="sello_discografico">Sellos discográficos</option>
              <option value="programa_institucional">Programas institucionales</option>
              <option value="plataforma_digital">Plataformas digitales</option>
              <option value="publicacion">Publicaciones</option>
            </select>
            {(muniFilter || tipoFilter || catFilter || textFilter) && (
              <button
                onClick={() => { setMuniFilter(''); setTipoFilter(''); setCatFilter(''); setTextFilter('') }}
                className="text-[9px] font-mono font-bold uppercase tracking-wider underline hover:no-underline"
              >
                Limpiar filtros
              </button>
            )}
          </div>

          {/* Categories */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
            {CAT_TABS.map(t => (
              <button
                key={t.value}
                onClick={() => setCatFilter(t.value)}
                className={`px-2.5 py-1 text-[9px] font-mono font-bold uppercase tracking-wider border border-black transition-all shrink-0 ${
                  catFilter === t.value ? 'bg-black text-white' : 'hover:bg-black/5'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {loading && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }, (_, i) => (
              <div key={i} className="animate-pulse border-2 border-black h-64" />
            ))}
          </div>
        )}

        {error && <p className="font-mono text-sm border-2 border-black p-4">{error}</p>}

        {!loading && !error && (
          <>
            {/* EVENTOS HOY highlight */}
            {(viewMode === 'todo' || viewMode === 'agenda') && filteredHoy.length > 0 && (
              <section className="mb-10">
                <div className="flex items-center gap-3 mb-4">
                  <span className="w-4 h-4 bg-red-600 animate-pulse" />
                  <h2 className="text-lg font-heading font-black uppercase tracking-wider">
                    Hoy en el Valle de Aburrá
                  </h2>
                  <span className="text-[10px] font-mono font-bold">{filteredHoy.length} evento{filteredHoy.length > 1 ? 's' : ''}</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {filteredHoy.map(ev => (
                    <EventCard key={ev.id} evento={ev} />
                  ))}
                </div>
                <div className="border-t-2 border-black mt-8" />
              </section>
            )}

            {/* AGENDA SECTION */}
            {(viewMode === 'todo' || viewMode === 'agenda') && filteredEventos.length > 0 && (
              <section className="mb-10">
                <div className="flex items-center gap-3 mb-4">
                  <span className="w-4 h-4 bg-black" style={{ clipPath: 'polygon(50% 0%, 0% 100%, 100% 100%)' }} />
                  <h2 className="text-lg font-heading font-black uppercase tracking-wider">
                    Próximos Eventos
                  </h2>
                  <Link to="/agenda" className="ml-auto text-[10px] font-mono font-bold uppercase tracking-wider hover:underline">
                    Ver agenda completa →
                  </Link>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {filteredEventos.slice(0, viewMode === 'agenda' ? 60 : 12).map(ev => (
                    <EventCard key={ev.id} evento={ev} />
                  ))}
                </div>
                {viewMode === 'todo' && filteredEventos.length > 12 && (
                  <div className="text-center mt-6">
                    <button
                      onClick={() => setViewMode('agenda')}
                      className="px-6 py-2.5 text-xs font-mono font-bold uppercase tracking-wider border-2 border-black hover:bg-black hover:text-white transition-all"
                    >
                      Ver {filteredEventos.length - 12} eventos más →
                    </button>
                  </div>
                )}
                <div className="border-t-2 border-black mt-8" />
              </section>
            )}

            {/* RED CULTURAL — Spaces grouped by tipo */}
            {(viewMode === 'todo' || viewMode === 'espacios') && filteredEspacios.length > 0 && (
              <>
                {/* Summary bar */}
                <section className="mb-6">
                  <div className="flex items-center gap-3 mb-4">
                    <span className="w-4 h-4 bg-black" />
                    <h2 className="text-lg font-heading font-black uppercase tracking-wider">
                      Red Cultural
                    </h2>
                    <span className="text-[10px] font-mono font-bold">{filteredEspacios.length} activos · scraping cada 6h</span>
                  </div>
                  <div className="flex items-center gap-2 flex-wrap mb-4">
                    {Object.entries(espaciosByTipo).map(([tipo, list]) => (
                      <button
                        key={tipo}
                        onClick={() => setTipoFilter(tipoFilter === tipo ? '' : tipo)}
                        className={`px-2 py-0.5 text-[9px] font-mono font-bold uppercase tracking-wider border border-black transition-all ${
                          tipoFilter === tipo ? 'bg-black text-white' : 'hover:bg-black/5'
                        }`}
                      >
                        {TIPO_LABELS[tipo]?.icon || '●'} {TIPO_LABELS[tipo]?.label || tipo.replaceAll('_', ' ')} ({list.length})
                      </button>
                    ))}
                  </div>
                </section>

                {/* Grouped sections */}
                {Object.entries(espaciosByTipo)
                  .sort(([, a], [, b]) => b.length - a.length)
                  .map(([tipo, list]) => {
                    const tipoInfo = TIPO_LABELS[tipo] || { label: tipo.replaceAll('_', ' '), icon: '●' }
                    const showLimit = viewMode === 'espacios' ? 100 : 8
                    return (
                      <section key={tipo} className="mb-8">
                        <div className="flex items-center gap-2 mb-3">
                          <span className="text-sm">{tipoInfo.icon}</span>
                          <h3 className="text-sm font-heading font-black uppercase tracking-wider">
                            {tipoInfo.label}
                          </h3>
                          <span className="text-[9px] font-mono font-bold opacity-50">{list.length}</span>
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-0 border-2 border-black">
                          {list.slice(0, showLimit).map((esp, i) => (
                            <div
                              key={esp.id}
                              className="group border-b border-r border-black p-5 hover:bg-black hover:text-white transition-all duration-300 relative"
                            >
                              <Link to={`/espacio/${esp.slug}`} className="absolute inset-0 z-10" />
                              <div className="flex justify-between items-start mb-2">
                                <span className="text-[9px] font-mono font-bold opacity-30 group-hover:opacity-100 tracking-wider">
                                  {String(i + 1).padStart(2, '0')}
                                </span>
                                <span className="text-[9px] font-mono font-bold uppercase tracking-wider border border-current px-1.5 py-0.5">
                                  {esp.categoria_principal.replaceAll('_', ' ')}
                                </span>
                              </div>
                              <h3 className="font-heading font-black text-sm uppercase tracking-wide leading-tight mb-2">
                                {esp.nombre}
                              </h3>
                              {esp.descripcion_corta && (
                                <p className="text-[10px] font-mono leading-relaxed opacity-50 group-hover:opacity-80 line-clamp-2 mb-2">
                                  {esp.descripcion_corta}
                                </p>
                              )}
                              <div className="flex items-center gap-2 text-[10px] font-mono opacity-50 group-hover:opacity-100 flex-wrap">
                                {esp.barrio && <span>◉ {esp.barrio}</span>}
                                <span>{esp.municipio}</span>
                              </div>
                              <div className="flex items-center gap-3 mt-2 relative z-20">
                                {esp.instagram_handle && (
                                  <a
                                    href={`https://instagram.com/${esp.instagram_handle.replace(/^@/, '')}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-[9px] font-mono font-bold opacity-40 hover:opacity-100 transition-opacity"
                                  >
                                    📸 @{esp.instagram_handle.replace(/^@/, '')}
                                  </a>
                                )}
                                {esp.sitio_web && (
                                  <a
                                    href={esp.sitio_web}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-[9px] font-mono font-bold opacity-40 hover:opacity-100 transition-opacity"
                                  >
                                    🌐 Web
                                  </a>
                                )}
                              </div>
                              <div className="flex items-center gap-2 mt-2">
                                <span className={`w-2 h-2 rounded-full ${
                                  esp.nivel_actividad === 'muy_activo' ? 'bg-green-500 animate-pulse' :
                                  esp.nivel_actividad === 'activo' ? 'bg-green-400' :
                                  esp.nivel_actividad === 'moderado' ? 'bg-yellow-400' : 'bg-gray-400'
                                }`} />
                                <span className="text-[8px] font-mono font-bold uppercase tracking-wider opacity-40 group-hover:opacity-80">
                                  {esp.nivel_actividad?.replaceAll('_', ' ')}
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                        {list.length > showLimit && viewMode === 'todo' && (
                          <div className="text-center mt-3">
                            <button
                              onClick={() => { setTipoFilter(tipo); setViewMode('espacios') }}
                              className="px-4 py-1.5 text-[10px] font-mono font-bold uppercase tracking-wider border-2 border-black hover:bg-black hover:text-white transition-all"
                            >
                              Ver {list.length - showLimit} más →
                            </button>
                          </div>
                        )}
                      </section>
                    )
                  })}
                <div className="border-t-2 border-black mt-4 mb-8" />
              </>
            )}

            {/* ZONAS */}
            {viewMode === 'todo' && zonas.length > 0 && (
              <section className="mb-10">
                <div className="flex items-center gap-3 mb-4">
                  <span className="w-4 h-4 bg-black rotate-45" />
                  <h2 className="text-lg font-heading font-black uppercase tracking-wider">
                    Zonas Culturales
                  </h2>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-0 border-2 border-black">
                  {zonas.map(z => (
                    <Link
                      key={z.id}
                      to={`/zona/${z.slug}`}
                      className="group border-b border-r border-black p-4 hover:bg-black hover:text-white transition-all"
                    >
                      <h3 className="font-heading font-black text-xs uppercase tracking-wide mb-1">{z.nombre}</h3>
                      <p className="text-[9px] font-mono opacity-50 group-hover:opacity-80 line-clamp-2">{z.vocacion}</p>
                      <span className="text-[8px] font-mono font-bold uppercase tracking-wider opacity-30 group-hover:opacity-100 mt-2 block">
                        {z.municipio} →
                      </span>
                    </Link>
                  ))}
                </div>
              </section>
            )}

            {/* Empty state */}
            {filteredEventos.length === 0 && filteredEspacios.length === 0 && (
              <div className="text-center py-16 border-2 border-dashed border-black">
                <p className="font-mono text-sm uppercase tracking-wider mb-2">
                  No se encontraron resultados{catFilter ? ` para "${catFilter.replaceAll('_', ' ')}"` : ''}.
                </p>
                {catFilter && (
                  <button
                    onClick={() => setCatFilter('')}
                    className="text-xs font-mono font-bold underline uppercase tracking-wider"
                  >
                    Limpiar filtro
                  </button>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </>
  )
}