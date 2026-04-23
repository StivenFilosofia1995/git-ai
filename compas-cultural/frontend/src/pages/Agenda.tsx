import { Helmet } from 'react-helmet-async'
import { useEffect, useState, useMemo, lazy, Suspense, Component, type ReactNode } from 'react'
import EventCard from '../components/agenda/EventCard'
import BuscarConAI from '../components/ui/BuscarConAI'
import HomeChatSection from '../components/chat/HomeChatSection'
import { commitEventosDescubiertos, discoverEventosAI, getEventos, getEventosHoy, getEventosSemana, getEventosProximasSemanas, getZonas, getStats, type Evento, type Zona } from '../lib/api'
import { formatEventDate } from '../lib/datetime'

const CulturalMap = lazy(() => import('../components/map/CulturalMap'))

class MapErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  state = { hasError: false }
  static getDerivedStateFromError() { return { hasError: true } }
  render() {
    if (this.state.hasError) {
      return (
        <div className="w-full h-[500px] border-2 border-black bg-gray-50 flex items-center justify-center">
          <p className="font-mono text-sm text-gray-400">No se pudo cargar el mapa</p>
        </div>
      )
    }
    return this.props.children
  }
}

const ITEMS_PER_PAGE = 24

/** Current date/time string in Colombia timezone */
function useColombiaClock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 60_000)
    return () => clearInterval(id)
  }, [])
  return now.toLocaleDateString('es-CO', {
    timeZone: 'America/Bogota',
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}


type TimeFilter = 'hoy' | 'semana' | 'proximas' | 'todos'
type PrecioFilter = '' | 'gratuito' | 'pago'

const MUNICIPIOS = [
  { value: '', label: 'Todos los municipios' },
  { value: 'medellin', label: 'Medellín' },
  { value: 'envigado', label: 'Envigado' },
  { value: 'itagui', label: 'Itagüí' },
  { value: 'bello', label: 'Bello' },
  { value: 'sabaneta', label: 'Sabaneta' },
  { value: 'la_estrella', label: 'La Estrella' },
  { value: 'copacabana', label: 'Copacabana' },
]

const TIME_LABELS: Record<TimeFilter, string> = {
  hoy: 'HOY',
  semana: 'SEMANA + PRÓXIMA',
  proximas: 'PRÓX 3 SEMANAS',
  todos: 'TODOS',
}

const TIME_DAYS_AHEAD: Record<TimeFilter, number> = {
  hoy: 0,
  semana: 14,
  proximas: 21,
  todos: 60,
}

const CAT_OPTIONS = [
  { value: '', label: 'Todas' },
  { value: 'teatro', label: 'Teatro' },
  { value: 'rock', label: 'Rock / Metal' },
  { value: 'hip_hop', label: 'Hip Hop' },
  { value: 'jazz', label: 'Jazz' },
  { value: 'galeria', label: 'Galerías' },
  { value: 'arte_contemporaneo', label: 'Arte Contemporáneo' },
  { value: 'libreria', label: 'Librerías' },
  { value: 'electronica', label: 'Electrónica' },
  { value: 'danza', label: 'Danza' },
  { value: 'musica_en_vivo', label: 'Música en vivo' },
  { value: 'poesia', label: 'Poesía' },
  { value: 'cine', label: 'Cine' },
  { value: 'festival', label: 'Festivales' },
  { value: 'fotografia', label: 'Fotografía' },
  { value: 'taller', label: 'Talleres' },
  { value: 'conferencia', label: 'Conferencias' },
]

function normalizeText(value: string | null | undefined): string {
  if (!value) return ''
  return value
    .normalize('NFD')
    .replaceAll(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replaceAll(/[_-]+/g, ' ')
    .replaceAll(/\s+/g, ' ')
    .trim()
}

function buildZonaTokens(zonaNombre: string): string[] {
  const base = normalizeText(zonaNombre)
  if (!base) return []
  const noParen = base.replaceAll(/\(.*?\)/g, '').trim()
  const noDash = noParen.replaceAll(/\s+-\s+/g, ' ').trim()
  const parts = noParen.split(/\s+-\s+/).map(t => t.trim()).filter(Boolean)
  return Array.from(new Set([base, noParen, noDash, ...parts].filter(Boolean)))
}

function inferTimeLabel(timeFilter: TimeFilter): string {
  if (timeFilter === 'hoy') return 'hoy'
  if (timeFilter === 'semana') return 'esta semana y la próxima'
  if (timeFilter === 'proximas') return 'próximas 3 semanas'
  return 'próximamente'
}

export default function Agenda() {
  const [eventos, setEventos] = useState<Evento[]>([])
  const [zonas, setZonas] = useState<Zona[]>([])
  const [stats, setStats] = useState({ espacios: 0, eventos: 0, zonas: 0 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [timeFilter, setTimeFilter] = useState<TimeFilter>('hoy')
  const [catFilter, setCatFilter] = useState('')
  const [zonaFilter, setZonaFilter] = useState('')
  const [textFilter, setTextFilter] = useState('')
  const [municipioFilter, setMunicipioFilter] = useState('')
  const [precioFilter, setPrecioFilter] = useState<PrecioFilter>('gratuito')
  const [page, setPage] = useState(1)
  const fechaActual = useColombiaClock()

  const runZonaScrape = async (limit = 15) => {
    const municipio = municipioFilter || undefined
    const zona = zonas.find(z => z.slug === zonaFilter)
    const tiempo = inferTimeLabel(timeFilter)
    const daysAhead = TIME_DAYS_AHEAD[timeFilter]
    const texto = [textFilter, zona?.nombre, tiempo].filter(Boolean).join(' ').trim() || undefined
    const res = await discoverEventosAI({
      municipio,
      categoria: catFilter || undefined,
      texto,
      max_queries: 2,
      max_results_per_query: Math.min(6, Math.max(3, Math.floor(limit / 3))),
      days_ahead: daysAhead,
      strict_categoria: Boolean(catFilter),
      auto_insert: false,
    })

    return {
      message: res.message,
      candidatos: res.result.candidatos ?? [],
      variables: {
        tipo_evento: catFilter || 'cultural',
        zona: zona?.nombre || municipioFilter || 'valle de aburra',
        fecha_actual: new Date().toISOString().slice(0, 10),
      },
    }
  }

  const reloadEventos = () => {
    const cargar = async () => {
      try {
        const municipioParam = municipioFilter || undefined
        if (timeFilter === 'hoy') {
          setEventos(await getEventosHoy(municipioParam))
        } else if (timeFilter === 'semana') {
          setEventos(await getEventosSemana())
        } else if (timeFilter === 'proximas') {
          setEventos(await getEventosProximasSemanas(21))
        } else {
          setEventos(await getEventos({ limit: 2000, municipio: municipioParam }))
        }
      } catch { /* silent */ }
    }
    void cargar()
  }

  useEffect(() => {
    getZonas().then(setZonas).catch(console.error)
    getStats().then(setStats).catch(() => {})
  }, [])

  useEffect(() => {
    const cargar = async () => {
      setLoading(true)
      setError(null)
      try {
        const municipioParam = municipioFilter || undefined
        if (timeFilter === 'hoy') {
          setEventos(await getEventosHoy(municipioParam))
        } else if (timeFilter === 'semana') {
          setEventos(await getEventosSemana())
        } else if (timeFilter === 'proximas') {
          setEventos(await getEventosProximasSemanas(21))
        } else {
          setEventos(await getEventos({ limit: 2000, municipio: municipioParam }))
        }
      } catch {
        setError('No fue posible cargar la agenda cultural.')
      } finally {
        setLoading(false)
      }
    }
    void cargar()
  }, [timeFilter, municipioFilter])

  const filtered = useMemo(() => {
    let result = eventos
    if (catFilter) {
      result = result.filter(e => e.categoria_principal === catFilter)
    }
    if (municipioFilter) {
      const m = normalizeText(municipioFilter)
      result = result.filter(e => normalizeText(e.municipio).includes(m))
    }
    if (precioFilter === 'gratuito') {
      result = result.filter(e => e.es_gratuito)
    } else if (precioFilter === 'pago') {
      result = result.filter(e => !e.es_gratuito)
    }
    if (zonaFilter) {
      const zona = zonas.find(z => z.slug === zonaFilter)
      if (zona) {
        const zonaTokens = buildZonaTokens(zona.nombre)
        result = result.filter(e => {
          const barrio = normalizeText(e.barrio)
          const lugar = normalizeText(e.nombre_lugar)
          return zonaTokens.some(t => barrio.includes(t) || lugar.includes(t))
        })
      }
    }
    if (textFilter.trim()) {
      const q = textFilter.trim().toLowerCase()
      result = result.filter(e =>
        e.titulo?.toLowerCase().includes(q) ||
        e.nombre_lugar?.toLowerCase().includes(q) ||
        e.barrio?.toLowerCase().includes(q) ||
        e.municipio?.toLowerCase().includes(q) ||
        e.descripcion?.toLowerCase().includes(q) ||
        e.categoria_principal?.toLowerCase().includes(q)
      )
    }
    return result
  }, [eventos, catFilter, zonaFilter, zonas, textFilter, municipioFilter, precioFilter])

  // Reset to page 1 whenever filters change
  useEffect(() => { setPage(1) }, [catFilter, zonaFilter, textFilter, municipioFilter, precioFilter, timeFilter])

  function getEmptyMsg(cat: string, zona: string, municipio: string, precio: PrecioFilter, time: TimeFilter): string {
    if (cat || zona) return 'No hay eventos con esos filtros.'
    if (municipio) return `No hay eventos en ${MUNICIPIOS.find(m => m.value === municipio)?.label ?? municipio}.`
    if (precio === 'gratuito') return 'No hay eventos gratuitos hoy.'
    if (time === 'hoy') return 'No hay eventos registrados para hoy.'
    return 'No hay eventos próximos.'
  }

  function getTimeLabel(t: TimeFilter): string {
    if (t === 'hoy') return ' hoy'
    if (t === 'semana') return ' esta semana y la próxima'
    if (t === 'proximas') return ' en las próximas 3 semanas'
    return ' próximos'
  }

  const totalPages = Math.ceil(filtered.length / ITEMS_PER_PAGE)
  const paged = filtered.slice((page - 1) * ITEMS_PER_PAGE, page * ITEMS_PER_PAGE)

  // Group events by date — force Colombia timezone
  const grouped = paged.reduce<Record<string, Evento[]>>((acc, ev) => {
    const dateKey = formatEventDate(ev.fecha_inicio, {
      weekday: 'long', day: 'numeric', month: 'long'
    })
    if (!acc[dateKey]) acc[dateKey] = []
    acc[dateKey].push(ev)
    return acc
  }, {})

  return (
    <>
      <Helmet>
        <title>Cultura ET&Eacute;REA &mdash; Agenda Cultural Medell&iacute;n</title>
        <meta name="description" content="Encuentra todo el mapa cultural de Medellín, oficial y no oficial. Teatro, Jazz, Hip-hop, Galerías, Spoken Word, Arte Underground — actualizado en tiempo real." />
      </Helmet>

      {/* ─── HERO ─────────────────────────────────────────────────────────────── */}
      <section className="relative bg-white border-b-2 border-black overflow-hidden min-h-[260px]">
        {/* Ilustración Medellín — img real para garantizar carga */}
        <img
          src="/medellin-ilustracion.png"
          alt=""
          aria-hidden="true"
          className="absolute right-0 bottom-0 h-full w-auto max-w-[55%] object-contain object-right-bottom pointer-events-none select-none"
          style={{ opacity: 0.32 }}
        />
        {/* Gradiente izquierdo suave — solo para legibilidad del texto */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{ background: 'linear-gradient(to right, rgba(255,255,255,0.97) 38%, rgba(255,255,255,0.5) 58%, rgba(255,255,255,0) 78%)' }}
          aria-hidden="true"
        />
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 pt-20 pb-10 lg:pt-28 lg:pb-14">
          {/* Live badge */}
          <div className="flex items-center gap-3 mb-8">
            <span className="block w-3 h-3 bg-black animate-pulse" />
            <span className="text-[11px] tracking-[0.3em] uppercase font-mono font-bold">
              Medellín · Valle de Aburrá · Live
            </span>
          </div>
          {/* Title */}
          <h1 className="font-black tracking-tighter leading-[0.88] mb-6">
            <span
              className="block text-black"
              style={{ fontSize: 'clamp(2.4rem, 7vw, 6rem)', fontFamily: "'Sora', 'Arial Black', sans-serif", fontWeight: 900 }}
            >
              Cultura
            </span>
            <span
              className="block"
              style={{
                fontSize: 'clamp(2.8rem, 9vw, 7.5rem)',
                fontFamily: "'Sora', 'Arial Black', sans-serif",
                fontWeight: 900,
                WebkitTextStroke: '2px black',
                WebkitTextFillColor: 'transparent',
                color: 'transparent',
              }}
            >
              ETÉREA
            </span>
          </h1>
          <p className="text-black/75 max-w-lg text-sm leading-relaxed mb-2 font-mono">
            Soy la IA que escucha el Valle de Aburrá en tiempo real.
          </p>
          <p className="text-black/50 max-w-md text-xs leading-relaxed mb-8 font-mono">
            Teatro · Jazz · Hip-hop · Galerías · Freestyle · Arte Underground · y todo lo que no aparece en ningún otro lado.
          </p>
          {/* Counters */}
          <div className="flex gap-8 mb-4">
            {[
              { n: stats.espacios, label: 'ESPACIOS' },
              { n: stats.eventos, label: 'EVENTOS' },
              { n: stats.zonas || zonas.length, label: 'ZONAS' },
            ].map(d => (
              <div key={d.label}>
                <div className="text-3xl font-black" style={{ fontFamily: "'Sora', 'Arial Black', sans-serif" }}>{d.n || '—'}</div>
                <div className="text-[9px] font-mono font-bold tracking-[0.2em] mt-0.5">{d.label}</div>
              </div>
            ))}
          </div>
          <p className="text-[10px] font-mono uppercase tracking-wider opacity-40">{fechaActual}</p>
        </div>
      </section>

      {/* ─── MARQUEE ──────────────────────────────────────────────────────────── */}
      <div className="bg-black text-white py-2.5 overflow-hidden border-b-2 border-black">
        <div className="animate-marquee whitespace-nowrap flex gap-8">
          {Array.from({ length: 2 }, (_, j) => (
            <span key={j} className="flex gap-8">
              {['TEATRO', 'ROCK', 'METAL', 'JAZZ', 'HIP-HOP', 'GALERÍAS', 'DANZA', 'ELECTRÓNICA', 'POESÍA', 'CINE', 'MURALISMO', 'FREESTYLE', 'EDITORIAL', 'CIRCO', 'FOTOGRAFÍA', 'PUNK'].map(cat => (
                <span key={`${j}-${cat}`} className="text-[11px] font-mono font-bold tracking-[0.3em] uppercase flex items-center gap-3">
                  <span className="w-1.5 h-1.5 bg-white" />
                  {cat}
                </span>
              ))}
            </span>
          ))}
        </div>
      </div>

      {/* ─── AGENDA: ¿QUÉ HAY HOY? + BUSCADOR + GRID ─────────────────────────── */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 pt-10 pb-8">
        {/* Encabezado de sección */}
        <div className="flex items-end justify-between mb-6 flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="w-3 h-3 bg-black" />
              <span className="text-[10px] font-mono font-bold tracking-[0.3em] uppercase">Agenda cultural</span>
            </div>
            <h2
              className="font-black tracking-tight uppercase leading-none"
              style={{ fontSize: 'clamp(1.8rem, 5vw, 3.2rem)', fontFamily: "'Sora', 'Arial Black', sans-serif" }}
            >
              Hoy en el Valle
            </h2>
          </div>
          <BuscarConAI
            label="Buscar con AI"
            onSearch={() => runZonaScrape(15)}
            onCommit={async candidatos => {
              const saved = await commitEventosDescubiertos(candidatos)
              return saved.message
            }}
            onComplete={reloadEventos}
          />
        </div>

        {/* Buscador de texto */}
        <div className="mb-4">
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm pointer-events-none">🔍</span>
            <input
              type="text"
              value={textFilter}
              onChange={e => setTextFilter(e.target.value)}
              placeholder="Filtrar por nombre, lugar, barrio, categoría..."
              className="w-full pl-9 pr-10 py-2.5 text-xs font-mono border-2 border-black focus:outline-none focus:ring-0 placeholder:text-neutral-400 bg-white"
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

        {/* Filtros — Fila 1: Tiempo + Precio + Municipio */}
        <div className="flex flex-wrap gap-0 mb-3 items-center">
          {/* Time */}
          <div className="flex">
            {(Object.keys(TIME_LABELS) as TimeFilter[]).map((key) => (
              <button
                key={key}
                onClick={() => setTimeFilter(key)}
                className={`px-4 py-2 text-[11px] font-mono font-bold uppercase tracking-wider border-2 border-black transition-all -ml-[2px] first:ml-0 ${
                  timeFilter === key ? 'bg-black text-white z-10' : 'bg-white text-black hover:bg-gray-100'
                }`}
              >
                {TIME_LABELS[key]}
              </button>
            ))}
          </div>
          {/* Precio */}
          <div className="flex ml-2">
            {([ ['', 'PRECIO'], ['gratuito', 'GRATIS'], ['pago', 'PAGO'] ] as [PrecioFilter, string][]).map(([val, label]) => (
              <button
                key={val}
                onClick={() => setPrecioFilter(val)}
                className={`px-3 py-2 text-[11px] font-mono font-bold uppercase tracking-wider border-2 border-black transition-all -ml-[2px] first:ml-0 ${
                  precioFilter === val ? 'bg-black text-white z-10' : 'bg-white text-black hover:bg-gray-100'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          {/* Municipio */}
          <select
            value={municipioFilter}
            onChange={e => setMunicipioFilter(e.target.value)}
            className="ml-2 px-3 py-2 text-[11px] font-mono font-bold uppercase tracking-wider border-2 border-black bg-white cursor-pointer focus:outline-none"
          >
            {MUNICIPIOS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
          {/* Zona */}
          {zonas.length > 0 && (
            <select
              value={zonaFilter}
              onChange={e => setZonaFilter(e.target.value)}
              className="ml-2 px-3 py-2 text-[11px] font-mono font-bold uppercase tracking-wider border-2 border-black bg-white cursor-pointer focus:outline-none"
            >
              <option value="">Todas las zonas</option>
              {zonas.map(z => (
                <option key={z.id} value={z.slug}>{z.nombre}</option>
              ))}
            </select>
          )}
          {(catFilter || zonaFilter || textFilter || municipioFilter || precioFilter) && (
            <button
              onClick={() => { setCatFilter(''); setZonaFilter(''); setTextFilter(''); setMunicipioFilter(''); setPrecioFilter('') }}
              className="text-[11px] font-mono font-bold uppercase tracking-wider ml-3 underline hover:no-underline"
            >
              ✕ Limpiar
            </button>
          )}
        </div>

        {/* Filtros — Fila 2: Categorías scrollables */}
        <div
          className="flex gap-2 overflow-x-auto pb-2 mb-6 -mx-4 px-4 sm:mx-0 sm:px-0"
          style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
        >
          {CAT_OPTIONS.map(opt => (
            <button
              key={opt.value}
              onClick={() => setCatFilter(opt.value)}
              className={`flex-shrink-0 px-3 py-1.5 text-[10px] font-mono font-bold uppercase tracking-wider border-2 border-black whitespace-nowrap transition-all ${
                catFilter === opt.value ? 'bg-black text-white' : 'bg-white text-black hover:bg-gray-100'
              }`}
            >
              {opt.value === '' ? '★ TODAS' : opt.label}
            </button>
          ))}
        </div>

        {/* Loading skeleton */}
        {loading && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {['sk1','sk2','sk3','sk4','sk5','sk6','sk7','sk8'].map(k => (
              <div key={k} className="animate-pulse border-2 border-black h-32 bg-gray-50" />
            ))}
          </div>
        )}

        {error && (
          <p className="text-black text-sm font-mono border-2 border-black p-4">{error}</p>
        )}

        {!loading && !error && filtered.length === 0 && (
          <div className="text-center py-14 border-2 border-dashed border-black space-y-4">
            <p className="font-mono text-sm uppercase tracking-wider">
              {getEmptyMsg(catFilter, zonaFilter, municipioFilter, precioFilter, timeFilter)}
            </p>
            <div className="flex justify-center">
              <BuscarConAI
                label="Buscar eventos con AI"
                onSearch={() => runZonaScrape(20)}
                onCommit={async candidatos => {
                  const saved = await commitEventosDescubiertos(candidatos)
                  return saved.message
                }}
                onComplete={reloadEventos}
              />
            </div>
          </div>
        )}

        {/* Grid compacto de eventos */}
        {!loading && !error && filtered.length > 0 && (
          <>
            <p className="text-[11px] font-mono font-bold uppercase tracking-wider mb-4">
              {filtered.length} evento{filtered.length === 1 ? '' : 's'}
              {getTimeLabel(timeFilter)}
              {totalPages > 1 && ` — pág. ${page} / ${totalPages}`}
            </p>

            {/* HOY: grid plano sin agrupar por fecha */}
            {timeFilter === 'hoy' ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                {paged.map(ev => (
                  <EventCard key={ev.id} evento={ev} />
                ))}
              </div>
            ) : (
              /* Semana/Todos: agrupado por fecha */
              <div className="space-y-6">
                {Object.entries(grouped).map(([dateLabel, dayEvents]) => (
                  <div key={dateLabel}>
                    <div className="flex items-center gap-3 mb-3">
                      <span className="w-2.5 h-2.5 bg-black" />
                      <h3 className="text-xs font-mono font-bold uppercase tracking-wider">{dateLabel}</h3>
                      <span className="text-[11px] font-mono opacity-60">{dayEvents.length} evento{dayEvents.length > 1 ? 's' : ''}</span>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                      {dayEvents.map(ev => (
                        <EventCard key={ev.id} evento={ev} />
                      ))}
                    </div>
                    <div className="border-t border-black/20 mt-5" />
                  </div>
                ))}
              </div>
            )}

            {/* Paginación */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between border-2 border-black p-3 mt-8">
                <button
                  onClick={() => { setPage(p => Math.max(1, p - 1)); window.scrollTo({ top: 480, behavior: 'smooth' }) }}
                  disabled={page === 1}
                  className="text-xs font-mono font-bold uppercase tracking-wider border-2 border-black px-4 py-2 disabled:opacity-30 hover:bg-black hover:text-white transition-all disabled:cursor-not-allowed"
                >
                  ← ANTERIOR
                </button>
                <span className="text-xs font-mono font-bold uppercase tracking-wider">{page} / {totalPages}</span>
                <button
                  onClick={() => { setPage(p => Math.min(totalPages, p + 1)); window.scrollTo({ top: 480, behavior: 'smooth' }) }}
                  disabled={page === totalPages}
                  className="text-xs font-mono font-bold uppercase tracking-wider border-2 border-black px-4 py-2 disabled:opacity-30 hover:bg-black hover:text-white transition-all disabled:cursor-not-allowed"
                >
                  SIGUIENTE →
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* ─── MAPA CULTURAL ───────────────────────────────────────────────────── */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-10 border-t-2 border-black">
        <div className="flex items-center gap-3 mb-6">
          <span className="w-4 h-4 bg-black" />
          <h2 className="text-xl font-black uppercase tracking-wider" style={{ fontFamily: "'Sora', 'Arial Black', sans-serif" }}>
            Mapa Cultural
          </h2>
          <span className="text-[11px] font-mono font-bold uppercase tracking-wider opacity-40">Valle de Aburrá</span>
        </div>
        <div className="border-2 border-black overflow-hidden">
          <MapErrorBoundary>
            <Suspense fallback={
              <div className="w-full h-[420px] bg-gray-50 flex items-center justify-center">
                <p className="font-mono text-sm text-gray-400 animate-pulse">Cargando mapa…</p>
              </div>
            }>
              <CulturalMap />
            </Suspense>
          </MapErrorBoundary>
        </div>
      </div>

      {/* ─── PREGÚNTALE A ETÉREA ─────────────────────────────────────────────── */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-10 border-t-2 border-black">
        <div className="flex items-center gap-3 mb-6">
          <span className="w-4 h-4 bg-black" />
          <h2 className="text-xl font-black uppercase tracking-wider" style={{ fontFamily: "'Sora', 'Arial Black', sans-serif" }}>
            Pregúntale a ETÉREA
          </h2>
          <span className="text-[11px] font-mono font-bold uppercase tracking-wider opacity-40">IA Cultural</span>
        </div>
        <HomeChatSection />
      </div>
    </>
  )
}
