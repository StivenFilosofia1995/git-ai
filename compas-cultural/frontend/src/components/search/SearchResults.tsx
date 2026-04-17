import { type ResultadoBusqueda } from '../../lib/api'

interface SearchResultsProps {
  resultados: ResultadoBusqueda[]
  loading?: boolean
}

export default function SearchResults({ resultados, loading }: Readonly<SearchResultsProps>) {
  if (loading) return <div className="text-center py-8">Buscando...</div>

  if (resultados.length === 0) {
    return (
      <div className="text-center py-8">
        <p className="font-mono text-sm">No se encontraron resultados.</p>
      </div>
    )
  }

  return (
    <div className="border-2 border-black">
      {resultados.map((resultado) => {
        const nombre = 'nombre' in resultado.item ? resultado.item.nombre : resultado.item.titulo
        const resultadoId = `${resultado.tipo}-${resultado.item.id}`
        const categoria = resultado.item.categoria_principal
        const barrio = resultado.item.barrio ?? 'Sin barrio'

        return (
        <div key={resultadoId} className="p-4 border-b-2 border-black last:border-b-0 hover:bg-black hover:text-white transition-all duration-300 group">
          <div className="flex justify-between items-start mb-2">
            <span className="text-[10px] font-mono font-bold uppercase tracking-wider border-2 border-current px-2 py-0.5">
              {resultado.tipo}
            </span>
            {typeof resultado.similitud === 'number' && (
              <span className="text-[10px] font-mono font-bold">
                {Math.round(resultado.similitud * 100)}%
              </span>
            )}
          </div>

          <h3 className="font-heading font-black text-sm uppercase tracking-wider mb-1">{nombre}</h3>
          <p className="text-[11px] font-mono">
            {categoria?.replaceAll('_', ' ')} · {barrio}
          </p>
        </div>
        )
      })}
    </div>
  )
}