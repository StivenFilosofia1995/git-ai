import { Helmet } from 'react-helmet-async'
import { useEffect, useState, useMemo, lazy, Suspense, Component, type ReactNode } from 'react'
import EventCard from '../components/agenda/EventCard'
import BuscarConAI from '../components/ui/BuscarConAI'
import EventosHoySection from '../components/agenda/EventosHoySection'
import HomeChatSection from '../components/chat/HomeChatSection'
import ColtejerWireframe from '../components/illustrations/ColtejerWireframe'
import { getEventos, getEventosHoy, getEventosSemana, getZonas, getStats, scrapeZona, type Evento, type Zona } from '../lib/api'

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

const CO_TZ = 'America/Bogota'
const ITEMS_PER_PAGE = 24

/** Current date/time string in Colombia timezone */
function useColombiaClock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 60_000)
    return () => clearInterval(id)
  }, [])
  return now.toLocaleDateString('es-CO', {
    timeZone: CO_TZ,
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}


type TimeFilter = 'hoy' | 'semana' | 'todos'
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
  semana: 'ESTA SEMANA',
  todos: 'PRÓXIMOS',
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

export default function Agenda() {
  const [eventos, setEventos] = useState<Evento[]>([])
  const [zonas, setZonas] = useState<Zona[]>([])
  const [stats, setStats] = useState({ espacios: 0, eventos: 0, zonas: 0 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [timeFilter, setTimeFilter] = useState<TimeFilter>('todos')
  const [catFilter, setCatFilter] = useState('')
  const [zonaFilter, setZonaFilter] = useState('')
  const [textFilter, setTextFilter] = useState('')
  const [municipioFilter, setMunicipioFilter] = useState('')
  const [precioFilter, setPrecioFilter] = useState<PrecioFilter>('')
  const [page, setPage] = useState(1)
  const fechaActual = useColombiaClock()

  const reloadEventos = () => {
    const cargar = async () => {
      try {
        if (timeFilter === 'hoy') {
          setEventos(await getEventosHoy())
        } else if (timeFilter === 'semana') {
          setEventos(await getEventosSemana())
        } else {
          setEventos(await getEventos({ limit: 60 }))
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
        if (timeFilter === 'hoy') {
          setEventos(await getEventosHoy())
        } else if (timeFilter === 'semana') {
          setEventos(await getEventosSemana())
        } else {
          setEventos(await getEventos({ limit: 60 }))
        }
      } catch {
        setError('No fue posible cargar la agenda cultural.')
      } finally {
        setLoading(false)
      }
    }
    void cargar()
  }, [timeFilter])

  const filtered = useMemo(() => {
    let result = eventos
    if (catFilter) {
      result = result.filter(e => e.categoria_principal === catFilter)
    }
    if (municipioFilter) {
      result = result.filter(e => e.municipio === municipioFilter)
    }
    if (precioFilter === 'gratuito') {
      result = result.filter(e => e.es_gratuito)
    } else if (precioFilter === 'pago') {
      result = result.filter(e => !e.es_gratuito)
    }
    if (zonaFilter) {
      const zona = zonas.find(z => z.slug === zonaFilter)
      if (zona) {
        result = result.filter(e =>
          e.barrio?.toLowerCase().includes(zona.nombre.toLowerCase()) ||
          e.nombre_lugar?.toLowerCase().includes(zona.nombre.toLowerCase())
        )
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

  const totalPages = Math.ceil(filtered.length / ITEMS_PER_PAGE)
  const paged = filtered.slice((page - 1) * ITEMS_PER_PAGE, page * ITEMS_PER_PAGE)

  // Group events by date — force Colombia timezone
  const grouped = paged.reduce<Record<string, Evento[]>>((acc, ev) => {
    const dateKey = new Date(ev.fecha_inicio).toLocaleDateString('es-CO', {
      timeZone: CO_TZ,
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
      <section className="relative bg-white border-b-2 border-black overflow-hidden">
        {/* Ilustración de fondo — Medellín */}
        <div
          className="absolute inset-0 bg-right-bottom bg-no-repeat"
          style={{
            backgroundImage: 'url(/medellin-ilustracion.png)',
            backgroundSize: 'contain',
            backgroundPosition: 'right bottom',
            opacity: 0.12,
          }}
          aria-hidden="true"
        />
        {/* Gradiente izquierdo para que el texto respire limpio */}
        <div
          className="absolute inset-0"
          style={{
            background: 'linear-gradient(to right, rgba(255,255,255,1) 40%, rgba(255,255,255,0) 75%)',
          }}
          aria-hidden="true"
        />
        <div className="relative max-w-7xl mx-auto px-6 pt-24 pb-16 lg:pt-32 lg:pb-24">
          <div className="flex items-start justify-between gap-12">
            <div className="max-w-2xl">
              {/* Live badge */}
              <div className="flex items-center gap-3 mb-10">
                <span className="block w-3 h-3 bg-black animate-pulse" />
                <span className="text-[11px] tracking-[0.3em] uppercase font-mono font-bold">
                  Medellín · Valle de Aburrá · Live
                </span>
              </div>

              {/* Title — same as image */}
              <h1 className="font-heading font-black tracking-tighter leading-[0.9] mb-8">
                <span
                  className="block text-black"
                  style={{ fontSize: 'clamp(2.5rem, 8vw, 6.5rem)', fontFamily: "'Sora', 'Arial Black', sans-serif", fontWeight: 900 }}
                >
                  Cultura
                </span>
                <span
                  className="block text-black"
                  style={{
                    fontSize: 'clamp(3rem, 10vw, 8rem)',
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

              {/* Description */}
              <p className="text-black max-w-md text-base leading-relaxed mb-4 font-mono">
                Teatro · Jazz · Hip-hop · Galerías ·{' '}
                Spoken Word · Arte Underground
                — actualizado en tiempo real.
              </p>
              <p className="text-black/60 max-w-md text-sm leading-relaxed mb-10 font-mono">
                Encuentra todo el mapa cultural de Medellín, oficial y no oficial.
                Soy una IA que trae toda la agenda.
              </p>

              {/* Real-time counters */}
              <div className="flex gap-8">
                {[
                  { n: stats.espacios, label: 'ESPACIOS' },
                  { n: stats.eventos, label: 'EVENTOS' },
                  { n: stats.zonas || zonas.length, label: 'ZONAS' },
                ].map(d => (
                  <div key={d.label}>
                    <div className="text-3xl font-heading font-black">{d.n || '—'}</div>
                    <div className="text-[9px] font-mono font-bold tracking-[0.2em] mt-1">{d.label}</div>
                  </div>
                ))}
              </div>

              {/* Clock */}
              <p className="text-[10px] font-mono uppercase tracking-wider mt-6 opacity-50">
                {fechaActual}
              </p>
            </div>

            {/* Coltejer wireframe */}
            <div className="hidden lg:block flex-shrink-0 -mr-8 mt-8">
              <ColtejerWireframe />
            </div>
          </div>
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

      {/* ─── ¿QUÉ HAY HOY? ───────────────────────────────────────────────────── */}
      <div className="relative max-w-7xl mx-auto px-6">
        {/* Marca de agua */}
        <div
          className="pointer-events-none absolute inset-0 bg-center bg-no-repeat bg-contain"
          style={{ backgroundImage: 'url(/medellin-ilustracion.png)', opacity: 0.04 }}
          aria-hidden="true"
        />
        <EventosHoySection />
      </div>

      {/* ─── CHAT AI ─────────────────────────────────────────────────────────── */}
      <div className="relative max-w-7xl mx-auto px-6">
        <div
          className="pointer-events-none absolute inset-0 bg-center bg-no-repeat bg-contain"
          style={{ backgroundImage: 'url(/medellin-ilustracion.png)', opacity: 0.04 }}
          aria-hidden="true"
        />
        <HomeChatSection />
      </div>

      {/* ─── MAPA CULTURAL ───────────────────────────────────────────────────── */}
      <div className="relative max-w-7xl mx-auto px-6 py-16 border-t-2 border-black">
        <div
          className="pointer-events-none absolute inset-0 bg-center bg-no-repeat bg-contain"
          style={{ backgroundImage: 'url(/medellin-ilustracion.png)', opacity: 0.04 }}
          aria-hidden="true"
        />
        <div className="flex items-center gap-3 mb-8">
          <span className="w-4 h-4 bg-black" />
          <h2 className="text-2xl font-heading font-black uppercase tracking-wider">Mapa Cultural</h2>
          <span className="text-[11px] font-mono font-bold uppercase tracking-wider opacity-50">Valle de Aburrá</span>
        </div>
        <div className="border-2 border-black overflow-hidden">
          <MapErrorBoundary>
            <Suspense fallback={
              <div className="w-full h-[500px] bg-gray-50 flex items-center justify-center">
                <p className="font-mono text-sm text-gray-400 animate-pulse">Cargando mapa…</p>
              </div>
            }>
              <CulturalMap />
            </Suspense>
          </MapErrorBoundary>
        </div>
      </div>

      {/* ─── AGENDA / FILTROS ────────────────────────────────────────────────── */}
      <div className="relative max-w-7xl mx-auto px-6 pb-20">
        <div
          className="pointer-events-none absolute inset-0 bg-center bg-no-repeat"
          style={{ backgroundImage: 'url(/medellin-ilustracion.png)', backgroundSize: '80%', opacity: 0.035 }}
          aria-hidden="true"
        />
        {/* Section header */}
        <div className="flex items-end justify-between mb-6 flex-wrap gap-4 border-t-2 border-black pt-16">
          <div>
            <div className="flex items-center gap-3 mb-3">
              <span className="w-3 h-3 bg-black" />
              <span className="text-[10px] font-mono font-bold tracking-[0.3em] uppercase">Agenda completa</span>
            </div>
            <h2 className="text-4xl md:text-5xl font-heading font-black tracking-tight uppercase">
              Próximos eventos
            </h2>
          </div>
          <BuscarConAI
            label="Buscar con AI"
            onSearch={async () => {
              const res = await scrapeZona('medellin', 15)
              return res.message
            }}
            onComplete={reloadEventos}
          />
        </div>

        {/* Text search */}
        <div className="mb-6">
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm">🔍</span>
            <input
              type="text"
              value={textFilter}
              onChange={e => setTextFilter(e.target.value)}
              placeholder="Filtrar por nombre, lugar, barrio, categoría..."
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

        {/* Filters row */}
        <div className="flex flex-wrap gap-0 mb-10 items-center">
          <div className="flex gap-0">
            {(Object.keys(TIME_LABELS) as TimeFilter[]).map((key) => (
              <button
                key={key}
                onClick={() => setTimeFilter(key)}
                className={`px-5 py-2 text-xs font-mono font-bold uppercase tracking-wider border-2 border-black transition-all duration-200 -ml-[2px] first:ml-0 ${
                  timeFilter === key ? 'bg-black text-white' : 'bg-white text-black hover:bg-black hover:text-white'
                }`}
              >
                {TIME_LABELS[key]}
              </button>
            ))}
          </div>

          <div className="w-[2px] h-8 bg-black hidden md:block mx-4" />

          <select
            value={catFilter}
            onChange={e => setCatFilter(e.target.value)}
            className="px-4 py-2 text-xs font-mono font-bold uppercase tracking-wider border-2 border-black bg-white cursor-pointer focus:outline-none"
          >
            {CAT_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>

          <select
            value={municipioFilter}
            onChange={e => setMunicipioFilter(e.target.value)}
            className="px-4 py-2 text-xs font-mono font-bold uppercase tracking-wider border-2 border-black bg-white cursor-pointer focus:outline-none -ml-[2px]"
          >
            {MUNICIPIOS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>

          <div className="flex gap-0 -ml-[2px]">
            {([ ['', 'PRECIO'], ['gratuito', 'GRATIS'], ['pago', 'PAGO'] ] as [PrecioFilter, string][]).map(([val, label]) => (
              <button
                key={val}
                onClick={() => setPrecioFilter(val)}
                className={`px-4 py-2 text-xs font-mono font-bold uppercase tracking-wider border-2 border-black transition-all duration-200 -ml-[2px] first:ml-0 ${
                  precioFilter === val ? 'bg-black text-white' : 'bg-white text-black hover:bg-black hover:text-white'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {zonas.length > 0 && (
            <select
              value={zonaFilter}
              onChange={e => setZonaFilter(e.target.value)}
              className="px-4 py-2 text-xs font-mono font-bold uppercase tracking-wider border-2 border-black bg-white cursor-pointer focus:outline-none -ml-[2px]"
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
              className="text-xs font-mono font-bold uppercase tracking-wider ml-4 hover:text-black transition-colors underline"
            >
              Limpiar filtros
            </button>
          )}
        </div>

        {loading && (
          <div className="space-y-4">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="animate-pulse border-2 border-black p-4 h-20" />
            ))}
          </div>
        )}

        {error && <p className="text-black text-sm font-mono border-2 border-black p-4">{error}</p>}

        {!loading && !error && filtered.length === 0 && (
          <div className="text-center py-16 border-2 border-dashed border-black space-y-4">
            <p className="font-mono text-sm uppercase tracking-wider">
              {(() => {
                if (catFilter || zonaFilter) return 'No hay eventos con esos filtros.'
                if (municipioFilter) return `No hay eventos en ${MUNICIPIOS.find(m => m.value === municipioFilter)?.label ?? municipioFilter}.`
                if (precioFilter === 'gratuito') return 'No hay eventos gratuitos próximos.'
                return 'No hay eventos próximos.'
              })()}
            </p>
            <div className="flex justify-center">
              <BuscarConAI
                label="Buscar eventos con AI"
                onSearch={async () => {
                  const res = await scrapeZona('medellin', 20)
                  return res.message
                }}
                onComplete={reloadEventos}
              />
            </div>
          </div>
        )}

        {!loading && !error && filtered.length > 0 && (
          <div className="space-y-8">
            <p className="text-[11px] font-mono font-bold uppercase tracking-wider">
              {filtered.length} evento{filtered.length === 1 ? '' : 's'} encontrado{filtered.length === 1 ? '' : 's'}
              {totalPages > 1 && ` — página ${page} de ${totalPages}`}
            </p>

            {Object.entries(grouped).map(([dateLabel, dayEvents]) => (
              <div key={dateLabel}>
                <div className="flex items-center gap-3 mb-4">
                  <span className="w-3 h-3 bg-black" />
                  <h3 className="text-sm font-mono font-bold uppercase tracking-wider">{dateLabel}</h3>
                  <span className="text-[11px] font-mono font-bold">{dayEvents.length} evento{dayEvents.length > 1 ? 's' : ''}</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {dayEvents.map((ev) => (
                    <EventCard key={ev.id} evento={ev} />
                  ))}
                </div>
                <div className="border-t-2 border-black mt-6" />
              </div>
            ))}

            {totalPages > 1 && (
              <div className="flex items-center justify-between border-2 border-black p-3">
                <button
                  onClick={() => { setPage(p => Math.max(1, p - 1)); window.scrollTo({ top: 0, behavior: 'smooth' }) }}
                  disabled={page === 1}
                  className="text-xs font-mono font-bold uppercase tracking-wider border-2 border-black px-4 py-2 disabled:opacity-30 hover:bg-black hover:text-white transition-all disabled:cursor-not-allowed"
                >
                  ← ANTERIOR
                </button>
                <span className="text-xs font-mono font-bold uppercase tracking-wider">{page} / {totalPages}</span>
                <button
                  onClick={() => { setPage(p => Math.min(totalPages, p + 1)); window.scrollTo({ top: 0, behavior: 'smooth' }) }}
                  disabled={page === totalPages}
                  className="text-xs font-mono font-bold uppercase tracking-wider border-2 border-black px-4 py-2 disabled:opacity-30 hover:bg-black hover:text-white transition-all disabled:cursor-not-allowed"
                >
                  SIGUIENTE →
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </>
  )
}
