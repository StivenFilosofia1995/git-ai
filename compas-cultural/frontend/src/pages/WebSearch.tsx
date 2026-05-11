import { Helmet } from 'react-helmet-async'
import { useState, useEffect } from 'react'
import BuscarConAI from '../components/ui/BuscarConAI'
import { commitEventosDescubiertos, discoverEventosConBarrio } from '../lib/api'

const HISTORY_KEY = 'websearch:history'
const MAX_HISTORY = 8

function loadHistory(): string[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY)
    return raw ? (JSON.parse(raw) as string[]) : []
  } catch {
    return []
  }
}

function saveToHistory(query: string, prev: string[]): string[] {
  const q = query.trim()
  if (!q) return prev
  const deduped = [q, ...prev.filter(h => h !== q)].slice(0, MAX_HISTORY)
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(deduped))
  } catch {
    // quota exceeded — ignore
  }
  return deduped
}

const QUICK_SEARCHES = [
  'Hip hop Medellín',
  'Teatro independiente',
  'Jazz esta semana',
  'Arte urbano gratis',
  'Danza contemporánea',
  'Poesía y literatura',
  'Conciertos barrio',
  'Festival cultural',
]

export default function WebSearch() {
  const [history, setHistory] = useState<string[]>([])
  const [selectedQuery, setSelectedQuery] = useState('')

  useEffect(() => {
    setHistory(loadHistory())
  }, [])

  function handleChip(q: string) {
    setSelectedQuery(q)
  }

  function clearHistory() {
    try {
      localStorage.removeItem(HISTORY_KEY)
    } catch {
      // ignore
    }
    setHistory([])
  }

  return (
    <>
      <Helmet>
        <title>Web Search Cultural | ETEREA</title>
        <meta
          name="description"
          content="Busca eventos culturales como un Google local por tema, barrio o colectivo y agrégalos al sistema."
        />
      </Helmet>

      <section className="border-b-2 border-black bg-white">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-12 sm:py-16">
          <div className="flex items-center gap-3 mb-4">
            <span className="w-3 h-3 bg-black" />
            <span className="text-[11px] font-mono font-bold uppercase tracking-[0.25em]">Módulo independiente</span>
          </div>
          <h1 className="text-3xl sm:text-5xl font-heading font-black uppercase tracking-tight mb-4">
            Web Search Cultural
          </h1>
          <p className="text-sm font-mono opacity-70 max-w-3xl">
            Aquí aportás al sistema cultural del Valle de Aburrá: buscá lo que no ves en el sistema.
          </p>
          <p className="text-xs font-mono opacity-50 mt-2 max-w-2xl">
            La búsqueda recorre la web en tiempo real — puede tomar hasta 60 segundos.
          </p>
        </div>
      </section>

      {/* Quick searches & history */}
      <section className="border-b border-black/10 bg-neutral-50">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-5">
          {history.length > 0 && (
            <div className="mb-4">
              <div className="flex items-center gap-3 mb-2">
                <span className="text-[10px] font-mono font-bold uppercase tracking-[0.2em] text-neutral-500">
                  Últimas búsquedas
                </span>
                <button
                  onClick={clearHistory}
                  className="text-[9px] font-mono text-neutral-400 hover:text-black uppercase tracking-widest underline ml-auto"
                >
                  Limpiar
                </button>
              </div>
              <div className="flex flex-wrap gap-2">
                {history.map(q => (
                  <button
                    key={q}
                    onClick={() => handleChip(q)}
                    className="px-3 py-1.5 border-2 border-black text-[11px] font-mono font-bold uppercase hover:bg-black hover:text-white transition-colors duration-150"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div>
            <span className="text-[10px] font-mono font-bold uppercase tracking-[0.2em] text-neutral-500 block mb-2">
              Búsquedas sugeridas
            </span>
            <div className="flex flex-wrap gap-2">
              {QUICK_SEARCHES.map(q => (
                <button
                  key={q}
                  onClick={() => handleChip(q)}
                  className="px-3 py-1.5 border border-black/30 text-[11px] font-mono uppercase hover:border-black hover:bg-yellow-100 transition-colors duration-150"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="max-w-5xl mx-auto px-4 sm:px-6 py-8 sm:py-10">
        <BuscarConAI
          key={selectedQuery}
          label="Buscar en web"
          allowTextInput
          searchPlaceholder="Escribe aquí — tema, barrio, colectivo, género musical…"
          initialQuery={selectedQuery}
          helperText="Aquí aportás al sistema cultural del Valle de Aburrá: buscá lo que no ves en el sistema."
          onSearch={async (query) => {
            const textQuery = (query || '').trim()
            if (textQuery) {
              setHistory(prev => saveToHistory(textQuery, prev))
            }
            const res = await discoverEventosConBarrio({
              texto: textQuery,
              max_queries: 4,
              max_results_per_query: 6,
              days_ahead: 45,
              strict_categoria: false,
              auto_insert: false,
            })
            return {
              message: res.message,
              candidatos: res.result.candidatos ?? [],
              variables: {
                tipo_evento: 'cultural',
                zona: 'valle de aburra',
                fecha_actual: new Date().toISOString().slice(0, 10),
              },
            }
          }}
          onCommit={async candidatos => {
            const saved = await commitEventosDescubiertos(candidatos)
            return saved.message
          }}
        />
      </section>
    </>
  )
}
