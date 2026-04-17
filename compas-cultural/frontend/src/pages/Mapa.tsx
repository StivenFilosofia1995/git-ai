import { Helmet } from 'react-helmet-async'
import CulturalMap from '../components/map/CulturalMap'

export default function Mapa() {
  return (
    <>
      <Helmet>
        <title>Mapa Cultural — Cultura ETÉREA</title>
      </Helmet>
      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="mb-6">
          <h1 className="text-2xl font-heading font-black tracking-tight uppercase">Mapa Cultural</h1>
          <p className="text-sm font-mono mt-1 uppercase tracking-wider">
            96 espacios culturales activos en el Valle de Aburrá
          </p>
        </div>
        <div className="overflow-hidden border-2 border-black">
          <CulturalMap />
        </div>
      </div>
    </>
  )
}
