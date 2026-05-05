import { Helmet } from 'react-helmet-async'
import BuscarConAI from '../components/ui/BuscarConAI'
import { commitEventosDescubiertos, discoverEventosConBarrio } from '../lib/api'

export default function WebSearch() {
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
            Aqui aportas al sistema cultural del Valle de Aburra: busca lo que no ves en el sistema.
          </p>
        </div>
      </section>

      <section className="max-w-5xl mx-auto px-4 sm:px-6 py-8 sm:py-10">
        <BuscarConAI
          label="Buscar en web"
          allowTextInput
          searchPlaceholder="Escribe aqui"
          helperText="Aqui aportas al sistema cultural del Valle de Aburra: busca lo que no ves en el sistema."
          onSearch={async (query) => {
            const textQuery = (query || '').trim()
            const res = await discoverEventosConBarrio({
              texto: textQuery,
              max_queries: 8,
              max_results_per_query: 10,
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
