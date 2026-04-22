import { useState, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { enviarMensajeChat, getEvento, type ChatMessage, type ChatResponse, type Evento } from '../../lib/api'
import { getEventDateParts } from '../../lib/datetime'

function stripMarkdown(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, '')
    .replace(/#{1,6}\s+/g, '')
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\*(.+?)\*/g, '$1')
    .replace(/`(.+?)`/g, '$1')
    .replace(/\[(.+?)\]\(.+?\)/g, '$1')
    .replace(/^[-*+]\s+/gm, '· ')
    .replace(/^\d+\.\s+/gm, '')
    .replace(/^>\s+/gm, '')
    .replace(/---/g, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

const SUGGESTIONS = [
  '¿Qué hay hoy en Medellín?',
  '¿Dónde hay jazz esta semana?',
  'Eventos gratis cerca al centro',
  'Teatro para este fin de semana',
]

export default function AISearchBar() {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [response, setResponse] = useState<ChatResponse | null>(null)
  const [eventos, setEventos] = useState<Evento[]>([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowSuggestions(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleAsk = async (pregunta: string) => {
    if (!pregunta.trim()) return
    setQuery(pregunta)
    setLoading(true)
    setShowSuggestions(false)
    setResponse(null)
    setEventos([])

    try {
      const historial: ChatMessage[] = []
      const res = await enviarMensajeChat(pregunta, historial)
      setResponse(res)

      const eventoFuentes = res.fuentes.filter(f => f.tipo === 'evento')
      if (eventoFuentes.length > 0) {
        const fetched = await Promise.allSettled(
          eventoFuentes.map(f => getEvento(f.nombre))
        )
        setEventos(
          fetched
            .filter((r): r is PromiseFulfilledResult<Evento> => r.status === 'fulfilled')
            .map(r => r.value)
        )
      }
    } catch {
      setResponse({ respuesta: 'No pude consultar en este momento. Intentá de nuevo.', fuentes: [] })
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    void handleAsk(query)
  }

  return (
    <div ref={containerRef} className="relative w-full max-w-xl">
      <form onSubmit={handleSubmit}>
        <div className="relative border-2 border-black bg-white">
          <div className="absolute left-4 top-1/2 -translate-y-1/2">
            {loading ? (
              <div className="w-4 h-4 border-2 border-black/20 border-t-black animate-spin" />
            ) : (
              <span className="text-black text-lg font-black">◆</span>
            )}
          </div>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => setShowSuggestions(true)}
            placeholder="Preguntale a ETÉREA… ¿qué hay hoy?"
            className="w-full pl-12 pr-24 py-4 bg-transparent focus:outline-none text-sm font-mono placeholder:text-black/30"
          />
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="absolute right-0 top-0 bottom-0 px-6 bg-black text-white text-[11px] font-mono font-bold uppercase tracking-wider hover:bg-white hover:text-black border-l-2 border-black transition-all duration-300 disabled:opacity-20 disabled:cursor-not-allowed"
          >
            {loading ? '...' : 'ASK'}
          </button>
        </div>
      </form>

      {showSuggestions && !response && !loading && (
        <div className="absolute top-full left-0 right-0 mt-0 bg-white border-2 border-t-0 border-black z-20">
          <div className="p-1">
            <p className="text-[9px] font-mono font-bold tracking-wider px-3 py-2 opacity-40">SUGERENCIAS</p>
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => void handleAsk(s)}
                className="w-full text-left px-3 py-2.5 text-sm font-mono text-black hover:bg-black hover:text-white transition-all duration-200"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {response && (
        <div className="absolute top-full left-0 right-0 mt-0 bg-white border-2 border-t-0 border-black z-20 max-h-[480px] overflow-y-auto">
          <div className="p-5">
            <div className="flex items-center gap-2 mb-4">
              <span className="w-3 h-3 bg-black" />
              <span className="text-[10px] font-mono font-bold tracking-wider uppercase">ETÉREA AI</span>
            </div>

            {/* Event cards */}
            {eventos.length > 0 && (
              <div className="space-y-2 mb-4">
                {eventos.map((ev) => {
                  const { diaCorto: dia, hora } = getEventDateParts(ev.fecha_inicio)
                  return (
                    <Link
                      key={ev.id}
                      to={`/evento/${ev.slug}`}
                      className="group flex gap-3 border-2 border-black hover:bg-black hover:text-white transition-all duration-200"
                    >
                      {ev.imagen_url && (
                        <div className="w-20 h-20 flex-shrink-0 overflow-hidden border-r-2 border-black">
                          <img src={ev.imagen_url} alt={ev.titulo} className="w-full h-full object-cover" loading="lazy" />
                        </div>
                      )}
                      <div className="py-2 pr-3 flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-[9px] font-mono font-bold uppercase tracking-wider border border-current px-1.5 py-0.5 leading-none">
                            {ev.categoria_principal.replaceAll('_', ' ')}
                          </span>
                          {ev.es_gratuito && (
                            <span className="text-[9px] font-mono font-bold uppercase tracking-wider border border-current px-1.5 py-0.5 leading-none">
                              Gratis
                            </span>
                          )}
                        </div>
                        <h4 className="text-xs font-heading font-black uppercase tracking-wide leading-snug truncate">
                          {ev.titulo}
                        </h4>
                        <div className="flex items-center gap-1.5 mt-1 text-[10px] font-mono opacity-70">
                          <span>{dia} · {hora}</span>
                          {ev.nombre_lugar && <span>· {ev.nombre_lugar}</span>}
                        </div>
                      </div>
                    </Link>
                  )
                })}
              </div>
            )}

            {/* Text response (markdown stripped) */}
            <p className="text-sm text-black leading-relaxed whitespace-pre-line font-mono">
              {stripMarkdown(response.respuesta)}
            </p>

            {/* Source links for espacios only (events already shown as cards) */}
            {response.fuentes.filter(f => f.tipo === 'espacio').length > 0 && (
              <div className="mt-4 pt-4 border-t-2 border-black">
                <p className="text-[9px] font-mono font-bold tracking-wider mb-2 opacity-40">ESPACIOS</p>
                <div className="flex flex-wrap gap-2">
                  {response.fuentes.filter(f => f.tipo === 'espacio').map((f) => (
                    <Link
                      key={f.id}
                      to={`/espacio/${f.nombre}`}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 border-2 border-black text-[10px] font-mono font-bold uppercase tracking-wider hover:bg-black hover:text-white transition-all duration-200"
                    >
                      <span className="w-1.5 h-1.5 bg-current" />
                      {f.nombre}
                    </Link>
                  ))}
                </div>
              </div>
            )}

            <button
              onClick={() => { setResponse(null); setEventos([]); setQuery('') }}
              className="mt-4 text-[10px] font-mono font-bold uppercase tracking-wider opacity-40 hover:opacity-100 transition-opacity"
            >
              ✕ Cerrar
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
