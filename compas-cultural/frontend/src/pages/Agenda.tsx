import { Helmet } from 'react-helmet-async'
import { useEffect, useState, useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import EventCard from '../components/agenda/EventCard'
import { getEventosHoy, getEventosProximasSemanas, getEventosTodos, getZonas, type Evento, type Zona } from '../lib/api'
import { bogotaDayKey, formatEventDate, hasReliableEventTime, parseEventDate } from '../lib/datetime'

/**
 * Página principal (/ y /agenda), pensada para el usuario perezoso:
 * lo primero que se ve son los eventos de HOY con hora, lugar y precio.
 * Atajos: Hoy · Esta noche · Este finde · 7 días · Gratis · Cerca de mí.
 * Todo lo demás (categoría, municipio, zona) vive en el panel "Filtros".
 */

type TimeFilter = 'hoy' | 'noche' | 'finde' | 'semana' | 'todos'

const TIME_OPTIONS: { value: TimeFilter; label: string }[] = [
  { value: 'hoy', label: 'Hoy' },
  { value: 'noche', label: 'Esta noche' },
  { value: 'finde', label: 'Este finde' },
  { value: 'semana', label: '7 días' },
  { value: 'todos', label: 'Todo' },
]

const TIME_TITLES: Record<TimeFilter, string> = {
  hoy: 'Hoy en el Valle',
  noche: 'Esta noche',
  finde: 'Este fin de semana',
  semana: 'Próximos 7 días',
  todos: 'Toda la agenda',
}

const MUNICIPIOS = [
  { value: '', label: 'Todo el Valle' },
  { value: 'medellin', label: 'Medellín' },
  { value: 'envigado', label: 'Envigado' },
  { value: 'itagui', label: 'Itagüí' },
  { value: 'bello', label: 'Bello' },
  { value: 'sabaneta', label: 'Sabaneta' },
  { value: 'la_estrella', label: 'La Estrella' },
  { value: 'copacabana', label: 'Copacabana' },
]

const CAT_OPTIONS = [
  { value: 'teatro', label: 'Teatro' },
  { value: 'musica_en_vivo', label: 'Música en vivo' },
  { value: 'rock', label: 'Rock / Metal' },
  { value: 'hip_hop', label: 'Hip hop' },
  { value: 'jazz', label: 'Jazz' },
  { value: 'electronica', label: 'Electrónica' },
  { value: 'danza', label: 'Danza' },
  { value: 'galeria', label: 'Galerías' },
  { value: 'arte_contemporaneo', label: 'Arte contemporáneo' },
  { value: 'cine', label: 'Cine' },
  { value: 'poesia', label: 'Poesía' },
  { value: 'libreria', label: 'Librerías' },
  { value: 'festival', label: 'Festivales' },
  { value: 'fotografia', label: 'Fotografía' },
  { value: 'taller', label: 'Talleres' },
  { value: 'conferencia', label: 'Charlas' },
]

const ITEMS_PER_PAGE = 24

function normalizeText(value: string | null | undefined): string {
  if (!value) return ''
  return value
    .normalize('NFD')
    .replaceAll(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replaceAll(/[_\-–—]+/g, ' ')
    .replaceAll(/\s+/g, ' ')
    .trim()
}

const SEARCH_SYNONYMS: Record<string, string[]> = {
  musica: ['concierto', 'show', 'en vivo', 'live', 'banda', 'artista'],
  concierto: ['musica', 'show', 'en vivo', 'live'],
  rock: ['metal', 'punk', 'grunge', 'indie'],
  metal: ['rock', 'punk', 'hardcore'],
  jazz: ['improvisacion', 'blues', 'swing'],
  hiphop: ['rap', 'freestyle', 'hip hop', 'urbano'],
  rap: ['freestyle', 'urbano'],
  danza: ['baile', 'coreografia', 'movimiento', 'ballet'],
  teatro: ['obra', 'actuacion', 'escena'],
  arte: ['galeria', 'exposicion', 'pintura', 'escultura', 'muestra'],
  cine: ['pelicula', 'film', 'corto', 'documental', 'proyeccion'],
  poesia: ['poema', 'spoken word', 'verso'],
  taller: ['curso', 'clase', 'workshop', 'formacion'],
  festival: ['fiesta', 'celebracion', 'feria'],
  electronica: ['techno', 'house', 'dj', 'electro'],
  fotografia: ['foto', 'imagen', 'visual'],
  muralismo: ['graffiti', 'arte urbano', 'street art'],
}

const PRICE_WORDS = /\b(gratis|gratuito|gratuita|libre|sin costo)\b/

function expandSearchTerms(raw: string): string[] {
  const base = normalizeText(raw).replace(PRICE_WORDS, '').replace(/\b(hoy|manana|esta noche)\b/g, '').trim()
  if (!base) return []
  const terms = [base, ...base.split(' ').filter(t => t.length > 2)]
  for (const [key, syns] of Object.entries(SEARCH_SYNONYMS)) {
    if (base.includes(key)) terms.push(...syns)
  }
  return Array.from(new Set(terms))
}

function zonaBaseName(nombre: string): string {
  return normalizeText(nombre.replaceAll(/\(.*?\)/g, '').split(' - ')[0])
}

function eventoMatchesZona(evento: Evento, zona: Zona): boolean {
  const token = zonaBaseName(zona.nombre)
  if (!token) return true
  const municipioZona = normalizeText(zona.municipio)
  const municipioEvento = normalizeText(evento.municipio)
  if (municipioZona && municipioEvento && !municipioEvento.includes(municipioZona)) return false
  return [evento.barrio, evento.nombre_lugar, evento.titulo]
    .map(normalizeText)
    .some(field => field.includes(token))
}

/** Hora (0-23) en Bogotá del inicio del evento, solo si la hora es confiable. */
function horaBogota(ev: Evento): number | null {
  if (!hasReliableEventTime(ev)) return null
  const d = parseEventDate(ev.fecha_inicio)
  if (!d) return null
  return Number(new Intl.DateTimeFormat('en-US', { timeZone: 'America/Bogota', hour: 'numeric', hour12: false }).format(d)) % 24
}

/** Días hasta el viernes (0 si ya es vie/sáb/dom) y hasta el lunes siguiente, en Bogotá. */
function ventanaFinde(): { desde: number; hasta: number } {
  const dow = new Date(new Date().toLocaleString('en-US', { timeZone: 'America/Bogota' })).getDay() // 0=dom
  const desde = dow === 0 || dow >= 5 ? 0 : 5 - dow
  const hasta = dow === 0 ? 1 : 8 - dow
  return { desde, hasta }
}

/** Ordena HOY: lo que viene primero; lo que ya empezó hace >3 h, al final. */
function ordenarHoy(eventos: Evento[]): Evento[] {
  const ahora = Date.now()
  const peso = (ev: Evento) => {
    const d = parseEventDate(ev.fecha_inicio)?.getTime() ?? ahora
    const confiable = hasReliableEventTime(ev)
    if (confiable && d < ahora - 3 * 3600_000) return 3e13 + d // ya pasó
    if (!confiable) return 2e13 + d // hora por confirmar: después de los que sí tienen hora
    return d
  }
  return [...eventos].sort((a, b) => peso(a) - peso(b))
}

function useFechaHoy() {
  return new Date().toLocaleDateString('es-CO', {
    timeZone: 'America/Bogota', weekday: 'long', day: 'numeric', month: 'long',
  })
}

const pill = (active: boolean) =>
  `shrink-0 min-h-[40px] px-3.5 text-sm font-bold border-2 border-black whitespace-nowrap transition-colors ${
    active ? 'bg-black text-white' : 'bg-white text-black hover:bg-black/5'
  }`

export default function Agenda() {
  const [params, setParams] = useSearchParams()
  const [eventos, setEventos] = useState<Evento[]>([])
  const [zonas, setZonas] = useState<Zona[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [timeFilter, setTimeFilter] = useState<TimeFilter>(() => {
    const t = params.get('cuando') as TimeFilter | null
    return t && TIME_OPTIONS.some(o => o.value === t) ? t : 'hoy'
  })
  const [gratis, setGratis] = useState(() => params.get('gratis') === '1')
  const [catFilter, setCatFilter] = useState(() => params.get('cat') ?? '')
  const [municipioFilter, setMunicipioFilter] = useState(() => params.get('municipio') ?? '')
  const [zonaFilter, setZonaFilter] = useState('')
  const [textFilter, setTextFilter] = useState(() => params.get('q') ?? '')
  const [filtrosAbiertos, setFiltrosAbiertos] = useState(false)
  const [page, setPage] = useState(1)
  const [reintento, setReintento] = useState(0)
  const fechaHoy = useFechaHoy()

  // Guardar los filtros principales en la URL (compartible, sobrevive al "atrás")
  useEffect(() => {
    const next = new URLSearchParams()
    if (timeFilter !== 'hoy') next.set('cuando', timeFilter)
    if (gratis) next.set('gratis', '1')
    if (catFilter) next.set('cat', catFilter)
    if (municipioFilter) next.set('municipio', municipioFilter)
    if (textFilter.trim()) next.set('q', textFilter.trim())
    setParams(next, { replace: true })
  }, [timeFilter, gratis, catFilter, municipioFilter, textFilter, setParams])

  useEffect(() => {
    getZonas().then(setZonas).catch(() => setZonas([]))
  }, [])

  useEffect(() => {
    let cancel = false
    const cargar = async () => {
      setLoading(true)
      setError(null)
      try {
        const filtros = {
          municipio: municipioFilter || undefined,
          categoria: catFilter || undefined,
          es_gratuito: gratis ? true : undefined,
        }
        let data: Evento[]
        if (timeFilter === 'hoy' || timeFilter === 'noche') {
          data = await getEventosHoy(filtros)
        } else if (timeFilter === 'finde') {
          const { desde, hasta } = ventanaFinde()
          data = await getEventosProximasSemanas(hasta, filtros, desde)
        } else if (timeFilter === 'semana') {
          data = await getEventosProximasSemanas(7, filtros, 0)
        } else {
          data = await getEventosTodos({ ...filtros, maxRows: 1500 })
        }
        if (!cancel) setEventos(data)
      } catch {
        if (!cancel) setError('No pudimos cargar la agenda. Revisa tu conexión e intenta de nuevo.')
      } finally {
        if (!cancel) setLoading(false)
      }
    }
    void cargar()
    return () => { cancel = true }
  }, [timeFilter, municipioFilter, catFilter, gratis, reintento])

  // Zonas sin duplicados ("Belén" / "Belen (Comuna 16)") y solo con eventos
  const zonasDisponibles = useMemo(() => {
    const vistas = new Set<string>()
    return zonas.filter(z => {
      const key = zonaBaseName(z.nombre)
      if (!key || vistas.has(key)) return false
      vistas.add(key)
      return eventos.some(ev => eventoMatchesZona(ev, z))
    })
  }, [zonas, eventos])

  const filtered = useMemo(() => {
    let result = eventos
    if (catFilter) result = result.filter(e => e.categoria_principal === catFilter || (e.categorias ?? []).includes(catFilter))
    if (gratis) result = result.filter(e => e.es_gratuito)
    if (municipioFilter) {
      const m = normalizeText(municipioFilter)
      result = result.filter(e => normalizeText(e.municipio).includes(m))
    }
    if (zonaFilter) {
      const zona = zonas.find(z => z.slug === zonaFilter)
      if (zona) result = result.filter(e => eventoMatchesZona(e, zona))
    }
    if (timeFilter === 'noche') {
      result = result.filter(e => (horaBogota(e) ?? -1) >= 17)
    }
    const q = textFilter.trim()
    if (q) {
      if (PRICE_WORDS.test(normalizeText(q))) result = result.filter(e => e.es_gratuito)
      const terms = expandSearchTerms(q)
      if (terms.length) {
        result = result.filter(e => {
          const searchable = [e.titulo, e.nombre_lugar, e.barrio, e.municipio, e.descripcion, e.categoria_principal]
            .map(normalizeText).join(' ')
          return terms.some(term => searchable.includes(term))
        })
      }
    }
    if (timeFilter === 'hoy' || timeFilter === 'noche') return ordenarHoy(result)
    return [...result].sort((a, b) => (a.fecha_inicio ?? '').localeCompare(b.fecha_inicio ?? ''))
  }, [eventos, catFilter, gratis, municipioFilter, zonaFilter, zonas, textFilter, timeFilter])

  useEffect(() => { setPage(1) }, [catFilter, zonaFilter, textFilter, municipioFilter, gratis, timeFilter])

  const totalPages = Math.ceil(filtered.length / ITEMS_PER_PAGE)
  const paged = filtered.slice((page - 1) * ITEMS_PER_PAGE, page * ITEMS_PER_PAGE)
  const filtrosActivos = [catFilter, municipioFilter, zonaFilter].filter(Boolean).length
  const agrupar = timeFilter !== 'hoy' && timeFilter !== 'noche'

  // Agrupar por día de Bogotá (los eventos en curso que empezaron antes quedan en "hoy")
  const hoyKey = bogotaDayKey(new Date()) ?? ''
  const grupos = useMemo(() => {
    if (!agrupar) return []
    const map = new Map<string, Evento[]>()
    for (const ev of paged) {
      let key = bogotaDayKey(ev.fecha_inicio) ?? hoyKey
      if (key < hoyKey) key = hoyKey
      if (!map.has(key)) map.set(key, [])
      map.get(key)!.push(ev)
    }
    return [...map.entries()].sort(([a], [b]) => a.localeCompare(b))
  }, [agrupar, paged, hoyKey])

  const limpiar = () => {
    setCatFilter(''); setZonaFilter(''); setTextFilter(''); setMunicipioFilter(''); setGratis(false)
  }

  const cambiarPagina = (p: number) => {
    setPage(p)
    document.getElementById('resultados')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <>
      <Helmet>
        <title>Cultura ETÉREA — Qué hacer hoy en Medellín y el Valle de Aburrá</title>
        <meta name="description" content="Planes culturales de hoy en Medellín y el Valle de Aburrá: teatro, conciertos, jazz, hip hop, galerías, cine y más, con hora, lugar y precio." />
      </Helmet>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 pt-4 sm:pt-6">
        <div className="flex items-baseline justify-between gap-3 flex-wrap">
          <h1 className="font-heading font-black tracking-tight leading-none text-[1.75rem] sm:text-4xl">
            {TIME_TITLES[timeFilter]}
          </h1>
          <p className="text-sm text-black/60 first-letter:uppercase">{fechaHoy}</p>
        </div>
      </div>

      {/* ─── Barra de atajos (sticky bajo el header) ─────────────────────── */}
      <div className="sticky top-14 z-30 bg-white/95 backdrop-blur border-b-2 border-black mt-3">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-2.5 space-y-2">
          <div className="relative">
            <label htmlFor="buscar-eventos" className="sr-only">Buscar eventos</label>
            <input
              id="buscar-eventos"
              type="search"
              value={textFilter}
              onChange={e => setTextFilter(e.target.value)}
              placeholder="¿Qué te provoca? jazz, teatro gratis, Casa Teatro…"
              className="w-full h-11 pl-3 pr-10 text-[15px] border-2 border-black focus:outline-none focus:ring-2 focus:ring-black/20 placeholder:text-black/40 bg-white"
            />
            {textFilter && (
              <button
                onClick={() => setTextFilter('')}
                aria-label="Limpiar búsqueda"
                className="absolute right-1 top-1/2 -translate-y-1/2 w-9 h-9 text-base font-bold hover:bg-black/5"
              >
                ✕
              </button>
            )}
          </div>

          <div className="relative">
            <div className="flex gap-1.5 overflow-x-auto pr-8 no-scrollbar" role="toolbar" aria-label="Atajos de agenda">
              {TIME_OPTIONS.map(opt => (
                <button key={opt.value} onClick={() => setTimeFilter(opt.value)} aria-pressed={timeFilter === opt.value} className={pill(timeFilter === opt.value)}>
                  {opt.label}
                </button>
              ))}
              <button onClick={() => setGratis(v => !v)} aria-pressed={gratis} className={pill(gratis)}>
                Gratis
              </button>
              <Link to="/cerca-de-ti" className={`${pill(false)} inline-flex items-center`}>
                📍 Cerca de mí
              </Link>
              <button
                onClick={() => setFiltrosAbiertos(v => !v)}
                aria-expanded={filtrosAbiertos}
                aria-controls="panel-filtros"
                className={pill(filtrosAbiertos || filtrosActivos > 0)}
              >
                Filtros{filtrosActivos > 0 ? ` (${filtrosActivos})` : ''} {filtrosAbiertos ? '▴' : '▾'}
              </button>
            </div>
            <div className="pointer-events-none absolute right-0 top-0 bottom-0 w-8 bg-gradient-to-l from-white to-transparent" aria-hidden="true" />
          </div>

          {filtrosAbiertos && (
            <div id="panel-filtros" className="border-2 border-black p-3 space-y-3 bg-white">
              <div>
                <p className="text-xs font-bold uppercase tracking-wider mb-1.5">Tipo de plan</p>
                <div className="flex flex-wrap gap-1.5">
                  {CAT_OPTIONS.map(opt => (
                    <button
                      key={opt.value}
                      onClick={() => setCatFilter(catFilter === opt.value ? '' : opt.value)}
                      aria-pressed={catFilter === opt.value}
                      className={`min-h-[36px] px-3 text-sm border-2 border-black transition-colors ${catFilter === opt.value ? 'bg-black text-white' : 'bg-white hover:bg-black/5'}`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <label className="text-xs font-bold uppercase tracking-wider">
                  Municipio
                  <select
                    value={municipioFilter}
                    onChange={e => { setMunicipioFilter(e.target.value); setZonaFilter('') }}
                    className="mt-1 block w-full h-11 px-2 text-sm normal-case tracking-normal font-normal border-2 border-black bg-white"
                  >
                    {MUNICIPIOS.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                  </select>
                </label>
                {(municipioFilter === '' || municipioFilter === 'medellin') && zonasDisponibles.length > 0 && (
                  <label className="text-xs font-bold uppercase tracking-wider">
                    Barrio o zona
                    <select
                      value={zonaFilter}
                      onChange={e => setZonaFilter(e.target.value)}
                      className="mt-1 block w-full h-11 px-2 text-sm normal-case tracking-normal font-normal border-2 border-black bg-white"
                    >
                      <option value="">Todas</option>
                      {zonasDisponibles.map(z => <option key={z.id} value={z.slug}>{z.nombre.replaceAll(/\s*\(.*?\)/g, '')}</option>)}
                    </select>
                  </label>
                )}
              </div>
              <div className="flex justify-between items-center">
                <button onClick={limpiar} className="text-sm underline hover:no-underline">Limpiar filtros</button>
                <button onClick={() => setFiltrosAbiertos(false)} className="min-h-[40px] px-4 text-sm font-bold bg-black text-white">
                  Ver {filtered.length} plan{filtered.length === 1 ? '' : 'es'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ─── Resultados ─────────────────────────────────────────────────── */}
      <section id="resultados" className="max-w-7xl mx-auto px-4 sm:px-6 pt-4 pb-10 scroll-mt-40">
        {loading && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4" aria-busy="true" aria-label="Cargando eventos">
            {Array.from({ length: 8 }, (_, i) => (
              <div key={i} className="border-2 border-black">
                <div className="aspect-[16/9] bg-black/5 motion-safe:animate-pulse" />
                <div className="p-4 space-y-2">
                  <div className="h-4 w-24 bg-black/10" />
                  <div className="h-5 w-full bg-black/10" />
                  <div className="h-4 w-2/3 bg-black/10" />
                </div>
              </div>
            ))}
          </div>
        )}

        {error && (
          <div className="border-2 border-black p-4 flex items-center justify-between gap-3 flex-wrap">
            <p className="text-sm">{error}</p>
            <button onClick={() => setReintento(n => n + 1)} className="text-sm font-bold underline">Reintentar</button>
          </div>
        )}

        {!loading && !error && filtered.length === 0 && (
          <div className="border-2 border-dashed border-black p-8 text-center space-y-3">
            <p className="font-bold text-lg">
              {timeFilter === 'noche' ? 'Aún no hay planes con hora para esta noche.' : 'No encontramos planes con estos filtros.'}
            </p>
            <div className="flex justify-center gap-2 flex-wrap">
              {timeFilter !== 'semana' && (
                <button onClick={() => setTimeFilter('semana')} className={pill(false)}>Ver próximos 7 días</button>
              )}
              {(filtrosActivos > 0 || gratis || textFilter) && (
                <button onClick={limpiar} className={pill(false)}>Quitar filtros</button>
              )}
            </div>
          </div>
        )}

        {!loading && !error && filtered.length > 0 && (
          <>
            <p className="text-sm text-black/60 mb-3">
              {filtered.length} plan{filtered.length === 1 ? '' : 'es'}
              {totalPages > 1 && ` · página ${page} de ${totalPages}`}
            </p>

            {!agrupar ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {paged.map(ev => <EventCard key={ev.id} evento={ev} />)}
              </div>
            ) : (
              <div className="space-y-8">
                {grupos.map(([dayKey, dayEvents]) => (
                  <div key={dayKey}>
                    <h2 className="font-heading font-black text-lg mb-3 first-letter:uppercase border-b-2 border-black pb-1">
                      {dayKey === hoyKey ? 'Hoy' : formatEventDate(`${dayKey}T12:00:00`, { weekday: 'long', day: 'numeric', month: 'long' })}
                      <span className="text-sm font-normal text-black/50 ml-2">{dayEvents.length}</span>
                    </h2>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                      {dayEvents.map(ev => <EventCard key={ev.id} evento={ev} />)}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {totalPages > 1 && (
              <nav className="flex items-center justify-between border-2 border-black p-2 mt-8" aria-label="Paginación">
                <button
                  onClick={() => cambiarPagina(Math.max(1, page - 1))}
                  disabled={page === 1}
                  className="min-h-[44px] px-4 text-sm font-bold border-2 border-black disabled:opacity-30 hover:bg-black hover:text-white transition-colors disabled:cursor-not-allowed"
                >
                  ← Anterior
                </button>
                <span className="text-sm font-bold">{page} / {totalPages}</span>
                <button
                  onClick={() => cambiarPagina(Math.min(totalPages, page + 1))}
                  disabled={page === totalPages}
                  className="min-h-[44px] px-4 text-sm font-bold border-2 border-black disabled:opacity-30 hover:bg-black hover:text-white transition-colors disabled:cursor-not-allowed"
                >
                  Siguiente →
                </button>
              </nav>
            )}
          </>
        )}
      </section>

      {/* ─── Secundario: mapa y aportes (debajo de los eventos) ─────────── */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 pb-12 grid gap-4 md:grid-cols-3">
        <Link to="/mapa" className="md:col-span-2 border-2 border-black p-5 bg-black text-white hover:bg-white hover:text-black transition-colors group">
          <p className="text-xs font-bold uppercase tracking-widest opacity-70 mb-1">Mapa cultural</p>
          <p className="font-heading font-black text-2xl">Mira en el mapa qué pasa cerca →</p>
          <p className="text-sm opacity-70 mt-1">Espacios, colectivos y los eventos de hoy en todo el Valle de Aburrá.</p>
        </Link>
        <div className="border-2 border-black p-5 space-y-2">
          <p className="text-xs font-bold uppercase tracking-widest text-black/60">¿Falta un plan?</p>
          <Link to="/publicar" className="block font-bold underline hover:no-underline">Publica tu evento gratis</Link>
          <Link to="/web-search" className="block text-sm underline hover:no-underline">Ayúdanos a encontrar eventos y colectivos</Link>
        </div>
      </section>
    </>
  )
}
