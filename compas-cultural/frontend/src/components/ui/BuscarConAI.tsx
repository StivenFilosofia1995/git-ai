import { useState } from 'react'
import { type DescubiertoEvento } from '../../lib/api'

interface Props {
  label?: string
  onSearch: () => Promise<string | { message: string; candidatos?: DescubiertoEvento[]; variables?: Record<string, string> }>
  onCommit?: (candidatos: DescubiertoEvento[]) => Promise<string>
  onComplete?: () => void
}

/**
 * Reusable "Buscar con AI" button.
 * onSearch should return a message string.
 * onComplete is called after search finishes (to refetch data).
 */
export default function BuscarConAI({ label = 'Buscar con AI', onSearch, onCommit, onComplete }: Readonly<Props>) {
  const [searching, setSearching] = useState(false)
  const [committing, setCommitting] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [candidatos, setCandidatos] = useState<DescubiertoEvento[]>([])
  const [variables, setVariables] = useState<Record<string, string>>({})

  const handleClick = async () => {
    setSearching(true)
    setMsg('Buscando eventos con inteligencia artificial...')
    setCandidatos([])
    setVariables({})
    try {
      const result = await onSearch()
      if (typeof result === 'string') {
        setMsg(result)
      } else {
        setMsg(result.message)
        setCandidatos(result.candidatos ?? [])
        setVariables(result.variables ?? {})
      }
      onComplete?.()
    } catch {
      setMsg('Error buscando eventos. Intentá de nuevo.')
    } finally {
      setSearching(false)
    }
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
          <><span>🔍</span><span>{label}</span></>
        )}
      </button>
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
