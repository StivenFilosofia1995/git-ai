import { Helmet } from 'react-helmet-async'
import { useEffect, useState, useMemo } from 'react'
import EventCard from '../components/agenda/EventCard'
import BuscarConAI from '../components/ui/BuscarConAI'
import { getEventos, getEventosHoy, getEventosSemana, getZonas, scrapeZona, type Evento, type Zona } from '../lib/api'

const CO_TZ = 'America/Bogota'

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

const TIME_LABELS: Record<TimeFilter, string> = {
  hoy: 'HOY',
  semana: 'ESTA SEMANA',
  todos: 'PRÓXIMOS',
}

const CAT_OPTIONS = [
  { value: '', label: 'Todas' },
  { value: 'teatro', label: 'Teatro' },
  { value: 'hip_hop', label: 'Hip Hop' },
  { value: 'jazz', label: 'Jazz' },
  { value: 'galeria', label: 'Galerías' },
  { value: 'libreria', label: 'Librerías' },
  { value: 'casa_cultura', label: 'Casas Cultura' },
  { value: 'electronica', label: 'Electrónica' },
  { value: 'danza', label: 'Danza' },
  { value: 'batalla_freestyle', label: 'Freestyle' },
  { value: 'musica_en_vivo', label: 'Música en vivo' },
  { value: 'poesia', label: 'Poesía' },
  { value: 'arte_contemporaneo', label: 'Arte contemporáneo' },
]

export default function Agenda() {
  const [eventos, setEventos] = useState<Evento[]>([])
  const [zonas, setZonas] = useState<Zona[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [timeFilter, setTimeFilter] = useState<TimeFilter>('todos')
  const [catFilter, setCatFilter] = useState('')
  const [zonaFilter, setZonaFilter] = useState('')
  const [textFilter, setTextFilter] = useState('')
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
  }, [eventos, catFilter, zonaFilter, zonas, textFilter])

  // Group events by date — force Colombia timezone
  const grouped = filtered.reduce<Record<string, Evento[]>>((acc, ev) => {
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
        <title>Agenda Cultural — Cultura ETÉREA</title>
      </Helmet>

      <div className="max-w-5xl mx-auto px-4 py-10">
        {/* Header */}
        <div className="flex items-end justify-between mb-6 flex-wrap gap-4">
          <div>
            <h1 className="text-4xl md:text-5xl font-heading font-black tracking-tight mb-2 uppercase">
              Agenda Cultural
            </h1>
            <p className="text-sm font-mono uppercase tracking-wider">
              Eventos en Medellín y el Valle de Aburrá
            </p>
            <p className="text-[10px] font-mono uppercase tracking-wider mt-1 opacity-60">
              {fechaActual}
            </p>
          </div>
          <BuscarConAI
            label="Buscar eventos con AI"
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
          {/* Time filter */}
          <div className="flex gap-0">
            {(Object.keys(TIME_LABELS) as TimeFilter[]).map((key) => (
              <button
                key={key}
                onClick={() => setTimeFilter(key)}
                className={`px-5 py-2 text-xs font-mono font-bold uppercase tracking-wider border-2 border-black transition-all duration-200 -ml-[2px] first:ml-0 ${
                  timeFilter === key
                    ? 'bg-black text-white'
                    : 'bg-white text-black hover:bg-black hover:text-white'
                }`}
              >
                {TIME_LABELS[key]}
              </button>
            ))}
          </div>

          <div className="w-[2px] h-8 bg-black hidden md:block mx-4" />

          {/* Category filter */}
          <select
            value={catFilter}
            onChange={e => setCatFilter(e.target.value)}
            className="px-4 py-2 text-xs font-mono font-bold uppercase tracking-wider border-2 border-black bg-white cursor-pointer focus:outline-none"
          >
            {CAT_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>

          {/* Zone filter */}
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

          {(catFilter || zonaFilter || textFilter) && (
            <button
              onClick={() => { setCatFilter(''); setZonaFilter(''); setTextFilter('') }}
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
              {catFilter || zonaFilter
                ? 'No hay eventos con esos filtros.'
                : 'No hay eventos próximos.'
              }
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
            {Object.entries(grouped).map(([dateLabel, dayEvents]) => (
              <div key={dateLabel}>
                <div className="flex items-center gap-3 mb-4">
                  <span className="w-3 h-3 bg-black" />
                  <h3 className="text-sm font-mono font-bold uppercase tracking-wider">
                    {dateLabel}
                  </h3>
                  <span className="text-[11px] font-mono font-bold">
                    {dayEvents.length} evento{dayEvents.length > 1 ? 's' : ''}
                  </span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {dayEvents.map((ev) => (
                    <EventCard key={ev.id} evento={ev} />
                  ))}
                </div>
                <div className="border-t-2 border-black mt-6" />
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  )
}