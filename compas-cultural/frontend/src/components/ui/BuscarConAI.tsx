import { useState } from 'react'
import { type DescubiertoEvento } from '../../lib/api'

interface Props {
  label?: string
  onSearch: (query?: string) => Promise<string | { message: string; candidatos?: DescubiertoEvento[]; variables?: Record<string, string> }>
  onCommit?: (candidatos: DescubiertoEvento[]) => Promise<string>
  onComplete?: () => void
  autoCommit?: boolean
  allowTextInput?: boolean
  searchPlaceholder?: string
  helperText?: string
  suggestions?: string[]
  initialQuery?: string
}

/**
 * Reusable "Buscar con AI" button.
 * onSearch should return a message string.
 * onComplete is called after search finishes (to refetch data).
 */
export default function BuscarConAI({
  label = 'Buscar con AI',
  onSearch,
  onCommit,
  onComplete,
  autoCommit = false,
  allowTextInput = false,
  searchPlaceholder = 'Busca por tema, barrio o colectivo',
  helperText,
  suggestions = [],
  initialQuery = '',
}: Readonly<Props>) {
  const [searching, setSearching] = useState(false)
  const [committing, setCommitting] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [candidatos, setCandidatos] = useState<DescubiertoEvento[]>([])
  const [variables, setVariables] = useState<Record<string, string>>({})
  const [query, setQuery] = useState(initialQuery)

  const handleSearch = async (queryOverride?: string) => {
    const effectiveQuery = (queryOverride ?? query).trim()
    setSearching(true)
    setMsg('Buscando eventos en la web...')
    setCandidatos([])
    setVariables({})
    try {
      const result = await onSearch(effectiveQuery || undefined)
      if (typeof result === 'string') {
        setMsg(result)
      } else {
        setMsg(result.message)
        const found = result.candidatos ?? []
        setCandidatos(found)
        setVariables(result.variables ?? {})

        if (autoCommit && onCommit && found.length > 0) {
          setCommitting(true)
          try {
            const saved = await onCommit(found)
            setMsg(`${result.message}\n${saved}`)
            setCandidatos([])
          } catch {
            setMsg(`${result.message}\nNo se pudieron agregar automáticamente los eventos al sistema.`)
          } finally {
            setCommitting(false)
          }
        }
      }
      onComplete?.()
    } catch {
      setMsg('Error buscando eventos. Intentá de nuevo.')
    } finally {
      setSearching(false)
    }
  }

  const handleClick = async () => {
    await handleSearch()
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (searching) return
    await handleSearch()
  }

  const handleCommit = async () => {
    if (!onCommit || candidatos.length === 0) return
    setCommitting(true)
    try {
      const r = await onCommit(candidatos)
      setMsg(r)
      setCandidatos([])
      onComplete?.()
    } catch {
      setMsg('No se pudieron agregar los eventos al sistema.')
    } finally {
      setCommitting(false)
    }
  }

  return (
    <div>
      {allowTextInput ? (
        <form onSubmit={handleSubmit} className="border-2 border-black bg-white">
          <div className="flex flex-col sm:flex-row">
            <input
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder={searchPlaceholder}
              className="flex-1 px-4 py-3 text-sm font-mono focus:outline-none"
            />
            <button
              type="submit"
              disabled={searching || !query.trim()}
              className="px-4 py-3 bg-black text-white text-[10px] font-mono font-bold uppercase tracking-wider hover:bg-neutral-800 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {searching ? (
                <>
                  <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin inline-block" />
                  <span>Buscando...</span>
                </>
              ) : (
                <>
                  <img
                    src="/icons/favicon.svg"
                    alt="ETÉREA"
                    className="w-3.5 h-3.5 object-contain"
                  />
                  <span>{label}</span>
                </>
              )}
            </button>
          </div>
          {(helperText || suggestions.length > 0) && (
            <div className="border-t border-black px-3 py-2">
              {helperText && (
                <p className="text-[11px] font-mono text-neutral-600 mb-2">{helperText}</p>
              )}
              {suggestions.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {suggestions.map(suggestion => (
                    <button
                      key={suggestion}
                      type="button"
                      onClick={() => {
                        setQuery(suggestion)
                        void handleSearch(suggestion)
                      }}
                      className="text-[10px] font-mono border border-black px-2 py-1 hover:bg-black hover:text-white transition-all"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </form>
      ) : (
        <button
          onClick={handleClick}
          disabled={searching}
          className="text-[10px] font-mono font-bold uppercase tracking-wider border-2 border-black px-3 py-1.5 hover:bg-black hover:text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          {searching ? (
            <>
              <span className="w-2 h-2 border-2 border-current border-t-transparent rounded-full animate-spin inline-block" />
              <span>Buscando...</span>
            </>
          ) : (
            <>
              <img
                src="/icons/favicon.svg"
                alt="ETÉREA"
                className="w-3.5 h-3.5 object-contain"
              />
              <span>{label}</span>
            </>
          )}
        </button>
      )}
      {msg && (
        <p className="text-xs font-mono text-neutral-500 mt-2 border border-neutral-300 px-3 py-2">
          {msg}
        </p>
      )}
      {candidatos.length > 0 && (
        <div className="mt-3 border-2 border-black p-3 bg-white">
          <p className="text-[10px] font-mono font-bold uppercase tracking-wider mb-2">
            Variables: tipo={variables.tipo_evento ?? 'cultural'} · zona={variables.zona ?? 'valle'} · fecha={variables.fecha_actual ?? '-'}
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 mb-3">
            {candidatos.slice(0, 9).map((ev, idx) => (
              <div key={`${ev.slug}-${idx}`} className="aspect-square border border-black p-2 overflow-hidden">
                <p className="text-[10px] font-mono font-bold uppercase leading-tight line-clamp-3">{ev.titulo}</p>
                <p className="text-[10px] font-mono mt-1 opacity-70 line-clamp-2">{ev.nombre_lugar ?? ev.municipio ?? 'Valle de Aburrá'}</p>
                <p className="text-[10px] font-mono mt-1 opacity-70 line-clamp-1">{ev.fecha_inicio?.slice(0, 10)}</p>
                <p className="text-[10px] font-mono mt-1 opacity-70 line-clamp-1">{ev.categoria_principal}</p>
                <div className="flex flex-wrap gap-2 mt-2">
                  {ev.imagen_url && (
                    <a
                      href={ev.imagen_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[9px] font-mono font-bold uppercase border border-black px-1.5 py-0.5 hover:bg-black hover:text-white transition-all"
                    >
                      Ver poster
                    </a>
                  )}
                  {ev.fuente_url && (
                    <a
                      href={ev.fuente_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[9px] font-mono font-bold uppercase border border-black px-1.5 py-0.5 hover:bg-black hover:text-white transition-all"
                    >
                      Abrir fuente
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
          <button
            onClick={handleCommit}
            disabled={!onCommit || committing}
            className="text-[10px] font-mono font-bold uppercase tracking-wider border-2 border-black px-3 py-1.5 hover:bg-black hover:text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {committing ? 'Guardando aporte...' : '¿Desea agregar al sistema estos eventos para otros habitantes del Valle?'}
          </button>
        </div>
      )}
    </div>
  )
}
