import { useState } from 'react'
import { Helmet } from 'react-helmet-async'
import BuscarConAI from '../components/ui/BuscarConAI'
import { commitEventosDescubiertos, discoverEventosConBarrio } from '../lib/api'

export default function WebSearch() {
  const [municipio, setMunicipio] = useState('medellin')
  const [barrio, setBarrio] = useState('')
  const [categoria, setCategoria] = useState('')

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
            <span className="text-[11px] font-mono font-bold uppercase tracking-[0.25em]">Modulo independiente</span>
          </div>
          <h1 className="text-3xl sm:text-5xl font-heading font-black uppercase tracking-tight mb-4">
            Web Search Cultural
          </h1>
          <p className="text-sm font-mono opacity-70 max-w-3xl">
            Escribe exactamente lo que quieres buscar. El motor prioriza tu texto y tu zona para encontrar resultados en la web
            y generar tarjetas candidatas para la agenda.
          </p>
        </div>
      </section>

      <section className="max-w-5xl mx-auto px-4 sm:px-6 py-8 sm:py-10">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-5">
          <select
            value={municipio}
            onChange={e => setMunicipio(e.target.value)}
            className="px-3 py-2 text-xs font-mono border-2 border-black bg-white focus:outline-none"
          >
            <option value="medellin">Medellin</option>
            <option value="envigado">Envigado</option>
            <option value="itagui">Itagui</option>
            <option value="bello">Bello</option>
            <option value="sabaneta">Sabaneta</option>
            <option value="la_estrella">La Estrella</option>
          </select>

          <input
            value={barrio}
            onChange={e => setBarrio(e.target.value)}
            placeholder="Barrio (ej: aranjuez)"
            className="px-3 py-2 text-xs font-mono border-2 border-black bg-white focus:outline-none"
          />

          <input
            value={categoria}
            onChange={e => setCategoria(e.target.value)}
            placeholder="Categoria (ej: rock, teatro, poesia)"
            className="px-3 py-2 text-xs font-mono border-2 border-black bg-white focus:outline-none"
          />
        </div>

        <BuscarConAI
          label="Buscar en web"
          allowTextInput
          searchPlaceholder="Ej: eventos de rock en aranjuez este fin de semana"
          helperText="Tip: mientras mas especifico el texto, mejores resultados."
          suggestions={[
            'eventos en aranjuez',
            'rock metal medellin',
            'teatro independiente envigado',
            'poesia y micro abierto laureles',
          ]}
          onSearch={async (query) => {
            const textQuery = (query || '').trim()
            const res = await discoverEventosConBarrio({
              municipio: municipio || undefined,
              barrio: barrio.trim() || undefined,
              categoria: categoria.trim() || undefined,
              texto: textQuery || [categoria, barrio, municipio].filter(Boolean).join(' '),
              max_queries: 6,
              max_results_per_query: 8,
              days_ahead: 30,
              strict_categoria: Boolean(categoria.trim()),
              auto_insert: false,
            })
            return {
              message: res.message,
              candidatos: res.result.candidatos ?? [],
              variables: {
                tipo_evento: categoria.trim() || 'cultural',
                zona: barrio.trim() || municipio || 'valle de aburra',
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
