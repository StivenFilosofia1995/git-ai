import { useState } from 'react'

interface Props {
  label?: string
  onSearch: () => Promise<string>
  onComplete?: () => void
}

/**
 * Reusable "Buscar con AI" button.
 * onSearch should return a message string.
 * onComplete is called after search finishes (to refetch data).
 */
export default function BuscarConAI({ label = 'Buscar con AI', onSearch, onComplete }: Props) {
  const [searching, setSearching] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

  const handleClick = async () => {
    setSearching(true)
    setMsg('Buscando eventos con inteligencia artificial...')
    try {
      const result = await onSearch()
      setMsg(result)
      onComplete?.()
    } catch {
      setMsg('Error buscando eventos. Intentá de nuevo.')
    } finally {
      setSearching(false)
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
            Buscando...
          </>
        ) : (
          <>🔍 {label}</>
        )}
      </button>
      {msg && (
        <p className="text-xs font-mono text-neutral-500 mt-2 border border-neutral-300 px-3 py-2">
          {msg}
        </p>
      )}
    </div>
  )
}
