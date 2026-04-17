import { Helmet } from 'react-helmet-async'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import SearchResults from '../components/search/SearchResults'
import SpaceGrid from '../components/spaces/SpaceGrid'
import { buscar, getEspacios, type Espacio, type ResultadoBusqueda } from '../lib/api'

export default function Explorar() {
  const [searchParams] = useSearchParams()
  const query = searchParams.get('q')?.trim() ?? ''

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [resultados, setResultados] = useState<ResultadoBusqueda[]>([])
  const [espacios, setEspacios] = useState<Espacio[]>([])

  useEffect(() => {
    const cargar = async () => {
      setLoading(true)
      setError(null)

      try {
        if (query) {
          const response = await buscar(query)
          setResultados(response.resultados)
          setEspacios([])
        } else {
          const listaEspacios = await getEspacios({ limit: 30 })
          setEspacios(listaEspacios)
          setResultados([])
        }
      } catch {
        setError('No fue posible cargar los resultados en este momento.')
      } finally {
        setLoading(false)
      }
    }

    void cargar()
  }, [query])

  return (
    <>
      <Helmet>
        <title>Explorar - Cultura ETÉREA</title>
      </Helmet>

      <div className="max-w-7xl mx-auto px-4 py-8">
        <h1 className="text-4xl font-mono font-bold mb-8">EXPLORAR</h1>

        {query ? (
          <p className="font-mono text-sm mb-6 uppercase tracking-wider">
            Resultados para: <span className="font-bold">{query}</span>
          </p>
        ) : (
          <p className="font-mono text-sm mb-6">Explora espacios culturales activos del Valle de Aburra.</p>
        )}

        {error ? <p className="font-mono text-sm border-2 border-black p-4">{error}</p> : null}

        {query ? (
          <SearchResults resultados={resultados} loading={loading} />
        ) : (
          <SpaceGrid espacios={espacios} loading={loading} />
        )}
      </div>
    </>
  )
}