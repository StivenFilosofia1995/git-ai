import { useState, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import EventCard from './EventCard'
import {
  discoverEventosAI,
  commitEventosDescubiertos,
  getEventosTodos,
  type Evento,
  type DescubiertoEvento,
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
  const [dbMsg, setDbMsg] = useState<string | null>(null)
  const [webMsg, setWebMsg] = useState<string | null>(null)
  const [similares, setSimilares] = useState<Evento[]>([])
  const [candidatos, setCandidatos] = useState<DescubiertoEvento[]>([])
  const [committing, setCommitting] = useState(false)
  const [commitMsg, setCommitMsg] = useState<string | null>(null)
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

  const buildTexto = (extra?: string) => {
    const parts: string[] = []
    if (extra?.trim()) parts.push(extra.trim())
    if (zonaLabel) parts.push(zonaLabel)
    if (catFilter) parts.push(catFilter.replaceAll('_', ' '))
    if (municipioFilter) parts.push(municipioFilter)
    if (!parts.length) parts.push('eventos culturales Medellín Valle de Aburrá')
    return parts.join(' ')
  }

  // ─── Auto-búsqueda al montar: BD + Web en paralelo ───────────────────────
  useEffect(() => {
    if (didAutoSearch.current) return
    didAutoSearch.current = true

    const autoSearch = async () => {
      setFase('auto')

      // BD y web en PARALELO
      const [dbResults, webRes] = await Promise.allSettled([
        cargarSimilares(),
        discoverEventosAI({
          municipio: municipioFilter || undefined,
          categoria: catFilter || undefined,
          texto: buildTexto(),
          max_queries: 3,
          max_results_per_query: 6,
          days_from: 0,
          days_ahead: 90,
          strict_categoria: Boolean(catFilter),
          auto_insert: false, // NO auto-insertar: mostramos al ciudadano para que confirme
        }),
      ])

      if (dbResults.status === 'fulfilled' && dbResults.value.length > 0) {
        setSimilares(dbResults.value)
        setDbMsg(`${dbResults.value.length} evento(s) encontrado(s) en la agenda`)
      }

      if (webRes.status === 'fulfilled') {
        const found = webRes.value.result?.candidatos ?? []
        if (found.length > 0) {
          setCandidatos(found)
          setWebMsg(`La IA encontró ${found.length} evento(s) en la web — confirmá para agregarlos`)
        } else {
          setWebMsg(webRes.value.message || 'No se encontraron eventos nuevos en la web.')
        }
      } else {
        setWebMsg('No fue posible buscar en la web ahora mismo.')
      }

      setFase('done')
    }

    void autoSearch()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ─── Búsqueda manual por texto del usuario ────────────────────────────────
  const buscar = async (texto: string) => {
    if (fase === 'searching' || fase === 'auto') return
    setFase('searching')
    setDbMsg(null)
    setWebMsg(null)
    setCommitMsg(null)
    setSimilares([])
    setCandidatos([])

    const [dbResults, webRes] = await Promise.allSettled([
      cargarSimilares(),
      discoverEventosAI({
        municipio: municipioFilter || undefined,
        categoria: catFilter || undefined,
        texto: buildTexto(texto),
        max_queries: 4,
        max_results_per_query: 8,
        days_from: 0,
        days_ahead: 90,
        strict_categoria: Boolean(catFilter),
        auto_insert: false,
      }),
    ])

    if (dbResults.status === 'fulfilled' && dbResults.value.length > 0) {
      setSimilares(dbResults.value)
      setDbMsg(`${dbResults.value.length} evento(s) en la agenda`)
    }

    if (webRes.status === 'fulfilled') {
      const found = webRes.value.result?.candidatos ?? []
      if (found.length > 0) {
        setCandidatos(found)
        setWebMsg(`La IA encontró ${found.length} evento(s) en la web — confirmá para agregarlos a la agenda`)
      } else {
        setWebMsg(webRes.value.message || 'No se encontraron eventos nuevos en la web.')
      }
    } else {
      setWebMsg('No fue posible buscar en la web. Verificá tu conexión.')
    }

    setFase('done')
  }

  // ─── Confirmar aporte ciudadano ───────────────────────────────────────────
  const handleCommit = async () => {
    if (candidatos.length === 0 || committing) return
    setCommitting(true)
    setCommitMsg(null)
    try {
      const res = await commitEventosDescubiertos(candidatos)
      setCommitMsg(res.message)
      setCandidatos([])
      // Recargar BD para mostrar los nuevos eventos
      const dbRefresh = await cargarSimilares()
      if (dbRefresh.length > 0) setSimilares(dbRefresh)
      onEventosFound([])
    } catch {
      setCommitMsg('Error al guardar los eventos. Intentá de nuevo.')
    } finally {
      setCommitting(false)
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
            ? 'Consultando la agenda y la web al mismo tiempo…'
            : 'Escribe qué te interesa — la IA busca en la web y vos confirmás el aporte'}
        </p>
      </div>

      {/* Indicador de búsqueda automática */}
      {buscando && (
        <div className="flex items-center justify-center gap-3">
          <span className="w-3 h-3 border-2 border-black border-t-transparent rounded-full animate-spin" />
          <span className="text-[11px] font-mono opacity-60">Buscando en agenda y web en paralelo…</span>
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
              (() => {
                if (zonaLabel) return `¿Qué buscás en ${zonaLabel}?`
                if (catFilter) return `¿Qué tipo de ${catFilter.replaceAll('_', ' ')} te interesa?`
                return '¿Qué querés hacer? Teatro, conciertos, talleres…'
              })()
            }
            disabled={buscando}
            className="flex-1 px-4 py-3 text-sm font-mono bg-white focus:outline-none placeholder:text-neutral-400 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={buscando || !query.trim()}
            className="px-5 py-3 bg-black text-white text-[10px] font-mono font-bold uppercase tracking-wider hover:bg-neutral-800 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {buscando ? (
              <>
                <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Buscando…</span>
              </>
            ) : (
              <span>Buscar</span>
            )}
          </button>
        </div>

        {/* Sugerencias rápidas */}
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

      {/* Mensajes de estado */}
      {(dbMsg || webMsg) && !buscando && (
        <div className="max-w-xl mx-auto space-y-1">
          {dbMsg && (
            <p className="text-[11px] font-mono text-neutral-600 border border-neutral-200 px-3 py-1.5 flex items-center gap-2">
              <span className="w-2 h-2 bg-black inline-block flex-shrink-0" />
              {dbMsg}
            </p>
          )}
          {webMsg && (
            <p className="text-[11px] font-mono text-neutral-600 border border-neutral-200 px-3 py-1.5 flex items-center gap-2">
              <span className="w-2 h-2 border-2 border-black inline-block flex-shrink-0" />
              {webMsg}
            </p>
          )}
        </div>
      )}

      {/* ── Aporte ciudadano: eventos encontrados en la web ── */}
      {candidatos.length > 0 && (
        <div className="border-2 border-black p-4 max-w-2xl mx-auto">
          <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
            <div>
              <p className="text-[10px] font-mono font-bold uppercase tracking-wider">
                ◆ Eventos encontrados en la web
              </p>
              <p className="text-[10px] font-mono opacity-50 mt-0.5">
                Revisá y confirmá para agregar a la agenda colectiva
              </p>
            </div>
            <button
              onClick={() => void handleCommit()}
              disabled={committing}
              className="text-[10px] font-mono font-bold uppercase tracking-wider bg-black text-white px-4 py-2 hover:bg-neutral-800 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {committing ? (
                <><span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" /> Guardando…</>
              ) : (
                `+ Agregar ${candidatos.length} evento(s) a la agenda`
              )}
            </button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {candidatos.slice(0, 8).map((ev, i) => (
              <div key={`${ev.slug ?? i}`} className="border border-black p-2 bg-white">
                <p className="text-[10px] font-mono font-bold uppercase leading-tight line-clamp-2">{ev.titulo}</p>
                <p className="text-[10px] font-mono opacity-60 mt-0.5">
                  {(() => {
                    const fecha = ev.fecha_inicio ? new Date(ev.fecha_inicio).toLocaleDateString('es-CO', { day: 'numeric', month: 'short' }) : '—'
                    const lugar = ev.nombre_lugar ?? ev.municipio ?? ''
                    return lugar ? `${fecha} · ${lugar}` : fecha
                  })()}
                </p>
                {ev.es_gratuito && (
                  <span className="text-[9px] font-mono border border-black px-1 mt-0.5 inline-block">GRATIS</span>
                )}
              </div>
            ))}
          </div>
          {candidatos.length > 8 && (
            <p className="text-[10px] font-mono opacity-40 mt-2 text-center">
              +{candidatos.length - 8} más
            </p>
          )}
        </div>
      )}

      {/* Mensaje post-commit */}
      {commitMsg && (
        <p className="text-[11px] font-mono text-center border border-black/20 max-w-xl mx-auto px-4 py-2">
          ✓ {commitMsg}
        </p>
      )}

      {/* Eventos de la agenda (BD amplia) */}
      {similares.length > 0 && (
        <div>
          <p className="text-[10px] font-mono font-bold uppercase tracking-wider mb-3 flex items-center gap-2">
            <span className="w-2 h-2 bg-black inline-block" />
            {(() => {
              const loc = zonaLabel ? ` — ${zonaLabel}` : catFilter ? ` — ${catFilter.replaceAll('_', ' ')}` : ''
              const filtroMsg = timeFilter !== 'todos' ? ' · fuera del filtro de fecha activo' : ''
              return `Próximos eventos en la agenda${loc}${filtroMsg}`
            })()}
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {similares.map(ev => (
              <EventCard key={ev.id} evento={ev} />
            ))}
          </div>
        </div>
      )}

      {/* CTA registrar colectivo */}
      <div className="border-t border-black/20 pt-5 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div>
          <p className="text-[11px] font-mono font-bold uppercase tracking-wider">
            {(() => {
              if (zonaFilter) return `¿Tenés un colectivo en ${zonaLabel || 'esta zona'}?`
              if (tieneContexto) return '¿Organizás eventos culturales?'
              return '¿Sos parte de un colectivo cultural?'
            })()}
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
