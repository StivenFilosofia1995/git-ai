import { useState, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import EventCard from './EventCard'
import {
  discoverEventosAI,
  commitEventosDescubiertos,
  getEventosTodos,
  type Evento,
} from '../../lib/api'

interface Props {
  catFilter: string
  zonaFilter: string
  zonaLabel: string
  municipioFilter: string
  timeFilter: string
  onEventosFound: (eventos: Evento[]) => void
}

export default function EmptyEstadoInteligente({
  catFilter,
  zonaFilter,
  zonaLabel,
  municipioFilter,
  timeFilter,
  onEventosFound,
}: Readonly<Props>) {
  const [query, setQuery] = useState('')
  const [fase, setFase] = useState<'idle' | 'auto' | 'searching' | 'done'>('idle')
  const [mensaje, setMensaje] = useState<string | null>(null)
  const [similares, setSimilares] = useState<Evento[]>([])
  const inputRef = useRef<HTMLInputElement>(null)
  const didAutoSearch = useRef(false)

  const tieneContexto = Boolean(catFilter || zonaFilter || municipioFilter)

  // ─── Búsqueda amplia en BD (sin restricción de fecha) ─────────────────────
  const cargarSimilares = async () => {
    const todos = await getEventosTodos({
      categoria: catFilter || undefined,
      barrio: zonaLabel || undefined,
      municipio: municipioFilter || undefined,
      maxRows: 30,
    })
    const hoyIso = new Date().toISOString()
    return todos
      .filter(e => e.fecha_inicio >= hoyIso)
      .sort((a, b) => a.fecha_inicio.localeCompare(b.fecha_inicio))
      .slice(0, 8)
  }

  // ─── Auto-búsqueda al montar ──────────────────────────────────────────────
  useEffect(() => {
    if (didAutoSearch.current) return
    didAutoSearch.current = true

    const autoSearch = async () => {
      setFase('auto')
      setMensaje('Buscando en la agenda y en la web…')

      try {
        // 1. BD amplia primero (inmediato)
        const dbResults = await cargarSimilares()
        if (dbResults.length > 0) setSimilares(dbResults)

        // 2. Web discovery con contexto del filtro actual
        const contextoParts: string[] = []
        if (zonaLabel) contextoParts.push(zonaLabel)
        if (catFilter) contextoParts.push(catFilter)
        if (municipioFilter) contextoParts.push(municipioFilter)
        if (!contextoParts.length) contextoParts.push('eventos culturales Medellín')

        const res = await discoverEventosAI({
          municipio: municipioFilter || undefined,
          categoria: catFilter || undefined,
          texto: contextoParts.join(' '),
          max_queries: 3,
          max_results_per_query: 6,
          days_from: 0,
          days_ahead: 90,
          strict_categoria: Boolean(catFilter),
          auto_insert: true,
        })

        const candidatos = res.result?.candidatos ?? []
        let saveMsg = ''
        if (candidatos.length > 0) {
          const saved = await commitEventosDescubiertos(candidatos)
          saveMsg = saved.message
        }

        // 3. Recargar BD luego de inserción para capturar lo nuevo
        const dbRefresh = await cargarSimilares()
        if (dbRefresh.length > 0) setSimilares(dbRefresh)

        const resumen = [res.message, saveMsg].filter(Boolean).join(' — ')
        setMensaje(resumen || 'Búsqueda completada.')

        // Señalar al padre que recargue con filtros normales
        onEventosFound([])
      } catch {
        setMensaje('No fue posible buscar en la web. Podés escribir una búsqueda manual.')
      } finally {
        setFase('done')
      }
    }

    void autoSearch()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ─── Búsqueda manual por texto del usuario ────────────────────────────────
  const buscar = async (texto: string) => {
    if (fase === 'searching' || fase === 'auto') return
    setFase('searching')
    setMensaje(null)
    setSimilares([])

    try {
      const dbResults = await cargarSimilares()
      if (dbResults.length > 0) setSimilares(dbResults)

      const contextoParts: string[] = []
      if (texto.trim()) contextoParts.push(texto.trim())
      if (zonaLabel) contextoParts.push(zonaLabel)
      if (catFilter) contextoParts.push(catFilter)

      const res = await discoverEventosAI({
        municipio: municipioFilter || undefined,
        categoria: catFilter || undefined,
        texto: contextoParts.join(' ') || undefined,
        max_queries: 4,
        max_results_per_query: 8,
        days_from: 0,
        days_ahead: 90,
        strict_categoria: Boolean(catFilter),
        auto_insert: true,
      })

      setMensaje(res.message)

      const candidatos = res.result?.candidatos ?? []
      if (candidatos.length > 0) {
        const saved = await commitEventosDescubiertos(candidatos)
        setMensaje(`${res.message} — ${saved.message}`)
      }

      // Recarga amplia post-inserción
      const dbRefresh = await cargarSimilares()
      if (dbRefresh.length > 0) setSimilares(dbRefresh)

      onEventosFound([])
    } catch {
      setMensaje('Error buscando. Intentá de nuevo.')
    } finally {
      setFase('done')
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    void buscar(query)
  }

  const handleSugerencia = (s: string) => {
    setQuery(s)
    void buscar(s)
  }

  const sugerencias = (() => {
    if (catFilter === 'teatro') return ['obras en cartelera', 'teatro comunitario gratuito', 'teatro experimental']
    if (catFilter === 'rock' || catFilter === 'metal') return ['conciertos de rock', 'bandas locales', 'festival de metal']
    if (catFilter === 'jazz') return ['jazz en vivo', 'noches de jazz', 'improvisación jazz']
    if (catFilter === 'danza') return ['clases de danza', 'danza contemporánea', 'ballet']
    if (catFilter === 'cine') return ['cine al aire libre', 'cineforo', 'cortos colombianos']
    if (catFilter === 'taller') return ['talleres creativos', 'taller de escritura', 'taller artístico gratuito']
    if (zonaLabel) return [`eventos en ${zonaLabel}`, `cultura en ${zonaLabel}`, `gratis en ${zonaLabel}`]
    if (timeFilter === 'hoy') return ['qué hay hoy', 'eventos gratis hoy', 'música en vivo hoy']
    return ['teatro esta semana', 'conciertos gratis', 'arte y cultura Medellín']
  })()

  const buscando = fase === 'auto' || fase === 'searching'

  return (
    <div className="border-2 border-dashed border-black p-8 space-y-6">
      {/* Título */}
      <div className="text-center">
        <p className="font-mono text-[11px] font-bold uppercase tracking-[0.25em] opacity-50 mb-1">
          {timeFilter === 'hoy' ? 'no hay eventos hoy con ese filtro' : 'no hay eventos con esos filtros'}
        </p>
        <h3
          className="font-black uppercase leading-tight"
          style={{ fontSize: 'clamp(1.1rem, 3vw, 1.8rem)', fontFamily: "'Sora', 'Arial Black', sans-serif" }}
        >
          Ayúdanos a buscar eventos
        </h3>
        <p className="text-xs font-mono opacity-60 mt-1">
          {buscando
            ? 'Consultando la web y la agenda…'
            : 'Escribe qué te interesa — la IA busca en la web, registra e integra a la agenda'}
        </p>
      </div>

      {/* Indicador de búsqueda automática */}
      {fase === 'auto' && (
        <div className="flex items-center justify-center gap-2">
          <span className="w-3 h-3 border-2 border-black border-t-transparent rounded-full animate-spin" />
          <span className="text-[11px] font-mono opacity-60">Buscando en la web…</span>
        </div>
      )}

      {/* Buscador manual */}
      <form onSubmit={handleSubmit} className="max-w-xl mx-auto">
        <div className="flex border-2 border-black">
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder={
              zonaLabel
                ? `¿Qué buscás en ${zonaLabel}?`
                : catFilter
                ? `¿Qué tipo de ${catFilter} te interesa?`
                : '¿Qué querés hacer? Teatro, conciertos, talleres…'
            }
            disabled={buscando}
            className="flex-1 px-4 py-3 text-sm font-mono bg-white focus:outline-none placeholder:text-neutral-400 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={buscando}
            className="px-5 py-3 bg-black text-white text-[10px] font-mono font-bold uppercase tracking-wider hover:bg-neutral-800 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {buscando ? (
              <>
                <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Buscando…</span>
              </>
            ) : (
              <>
                <img src="/icons/favicon.svg" alt="" className="w-3 h-3 object-contain" />
                <span>Buscar</span>
              </>
            )}
          </button>
        </div>

        {/* Sugerencias rápidas — solo cuando idle o done */}
        {(fase === 'idle' || fase === 'done') && (
          <div className="flex flex-wrap gap-1.5 mt-2">
            {sugerencias.map(s => (
              <button
                key={s}
                type="button"
                onClick={() => handleSugerencia(s)}
                className="text-[10px] font-mono border border-black px-2 py-1 hover:bg-black hover:text-white transition-all"
              >
                {s}
              </button>
            ))}
          </div>
        )}
      </form>

      {/* Mensaje de resultado */}
      {mensaje && (
        <p className="text-[11px] font-mono text-neutral-500 text-center border border-neutral-300 max-w-xl mx-auto px-4 py-2 whitespace-pre-line">
          {mensaje}
        </p>
      )}

      {/* Eventos encontrados (BD amplia o web) */}
      {similares.length > 0 && (
        <div className="mt-2">
          <p className="text-[10px] font-mono font-bold uppercase tracking-wider mb-3 flex items-center gap-2">
            <span className="w-2 h-2 bg-black inline-block" />
            {similares.some(e => {
              const hoy = new Date().toISOString().slice(0, 10)
              return e.fecha_inicio.slice(0, 10) === hoy
            })
              ? 'Eventos encontrados'
              : 'Próximos eventos'}
            {zonaLabel ? ` en ${zonaLabel}` : catFilter ? ` de ${catFilter}` : ''}
            {timeFilter !== 'todos' && (
              <span className="opacity-50 font-normal normal-case tracking-normal">
                — pueden estar fuera del filtro de fecha
              </span>
            )}
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {similares.map(ev => (
              <EventCard key={ev.id} evento={ev} />
            ))}
          </div>
          {timeFilter !== 'todos' && (
            <p className="text-[10px] font-mono opacity-50 mt-3 text-center">
              Para ver todos sin restricción de fecha, seleccioná{' '}
              <strong>TODOS</strong> en los filtros de arriba
            </p>
          )}
        </div>
      )}

      {/* CTA registrar colectivo */}
      <div className="border-t border-black/20 pt-5 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div>
          <p className="text-[11px] font-mono font-bold uppercase tracking-wider">
            {zonaFilter
              ? `¿Tenés un colectivo en ${zonaLabel || 'esta zona'}?`
              : tieneContexto
              ? '¿Organizás eventos culturales?'
              : '¿Sos parte de un colectivo cultural?'}
          </p>
          <p className="text-[10px] font-mono opacity-50 mt-0.5">
            Registrá tu espacio y tus eventos para que aparezcan en la agenda
          </p>
        </div>
        <Link
          to="/registrar"
          className="text-[10px] font-mono font-bold uppercase tracking-wider border-2 border-black px-4 py-2 hover:bg-black hover:text-white transition-all whitespace-nowrap"
        >
          + Registrar colectivo
        </Link>
      </div>
    </div>
  )
}
