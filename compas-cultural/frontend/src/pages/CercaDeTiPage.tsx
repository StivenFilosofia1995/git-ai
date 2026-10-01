import { Helmet } from 'react-helmet-async'
import CercaDeTi from '../components/agenda/CercaDeTi'

export default function CercaDeTiPage() {
  return (
    <>
      <Helmet>
        <title>Cerca de mí — Cultura ETÉREA</title>
        <meta name="description" content="Planes culturales cerca de ti en el Valle de Aburrá, ordenados por distancia real." />
      </Helmet>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-5 sm:py-8">
        <h1 className="font-heading font-black tracking-tight leading-none text-[1.75rem] sm:text-4xl mb-1">
          Cerca de mí
        </h1>
        <p className="text-sm text-black/60 mb-4">
          Planes culturales ordenados por distancia: teatro, música, arte y más.
        </p>
        <CercaDeTi />
      </div>
    </>
  )
}
