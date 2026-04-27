import { Link } from 'react-router-dom'
import { type ResultadoBusqueda } from '../../lib/api'

interface SearchResultsProps {
  resultados: ResultadoBusqueda[]
  loading?: boolean
}

export default function SearchResults({ resultados, loading }: Readonly<SearchResultsProps>) {
  if (loading) return (
    <div className="flex items-center justify-center gap-2 py-12">
      <span className="w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin" />
      <span className="font-mono text-sm">Buscando…</span>
    </div>
  )

  if (resultados.length === 0) {
    return (
      <div className="text-center py-8">
        <p className="font-mono text-sm">No se encontraron resultados.</p>
      </div>
    )
  }

  return (
    <div className="border-2 border-black divide-y-2 divide-black">
      {resultados.map((resultado) => {
        const esEvento = resultado.tipo === 'evento'
        const nombre = 'nombre' in resultado.item ? resultado.item.nombre : resultado.item.titulo
        const slug = resultado.item.slug
        const href = esEvento ? `/evento/${slug}` : `/espacio/${slug}`
        const resultadoId = `${resultado.tipo}-${resultado.item.id}`
        const categoria = resultado.item.categoria_principal
        const barrio = resultado.item.barrio ?? null
        const imagen = 'imagen_url' in resultado.item ? resultado.item.imagen_url : null
        const fecha = esEvento && 'fecha_inicio' in resultado.item
          ? new Date(resultado.item.fecha_inicio).toLocaleDateString('es-CO', { day: 'numeric', month: 'short', year: 'numeric' })
          : null

        return (
          <Link
            key={resultadoId}
            to={href}
            className="flex gap-4 p-4 hover:bg-black hover:text-white transition-all duration-200 group"
          >
            {imagen && (
              <div className="w-16 h-16 flex-shrink-0 overflow-hidden border-2 border-current">
                <img src={imagen} alt={nombre} className="w-full h-full object-cover" />
              </div>
            )}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1 flex-wrap">
                <span className="text-[9px] font-mono font-bold uppercase tracking-wider border-2 border-current px-1.5 py-0.5 leading-none">
                  {resultado.tipo}
                </span>
                {categoria && (
                  <span className="text-[9px] font-mono opacity-60 uppercase tracking-wider">
                    {categoria.replaceAll('_', ' ')}
                  </span>
                )}
                {typeof resultado.similitud === 'number' && (
                  <span className="text-[9px] font-mono opacity-40 ml-auto">
                    {Math.round(resultado.similitud * 100)}%
                  </span>
                )}
              </div>
              <h3 className="font-heading font-black text-sm uppercase tracking-wide leading-snug truncate">{nombre}</h3>
              <p className="text-[10px] font-mono opacity-60 mt-0.5">
                {[barrio, fecha].filter(Boolean).join(' · ')}
              </p>
            </div>
            <span className="text-lg font-mono self-center opacity-0 group-hover:opacity-100 transition-opacity">→</span>
          </Link>
        )
      })}
    </div>
  )
}