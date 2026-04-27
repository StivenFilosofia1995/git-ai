import { Helmet } from 'react-helmet-async'
import CercaDeTi from '../components/agenda/CercaDeTi'

export default function CercaDeTiPage() {
  return (
    <>
      <Helmet>
        <title>Cerca de Ti — Cultura ETÉREA</title>
        <meta name="description" content="Eventos y espacios culturales cerca de tu ubicación en el Valle de Aburrá" />
      </Helmet>

      <div className="max-w-7xl mx-auto px-6 py-12">
        <div className="flex items-center gap-3 mb-6">
          <span className="w-3 h-3 bg-black animate-pulse rounded-full" />
          <span className="text-[11px] tracking-[0.3em] uppercase font-mono font-bold">
            Tu zona · Valle de Aburrá
          </span>
        </div>

        <h1 className="text-5xl md:text-7xl font-heading font-black tracking-tighter uppercase leading-[0.9] mb-4">
          Cerca<br />de Ti
        </h1>

        <p className="text-sm font-mono leading-relaxed max-w-lg mb-10 text-neutral-600">
          Poné tu ubicación y te mostramos los eventos y espacios culturales más cercanos — teatro, música, arte y más.
        </p>

        <CercaDeTi />
      </div>
    </>
  )
}
