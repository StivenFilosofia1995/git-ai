import { lazy, Suspense, Component, type ReactNode } from 'react'
import { Helmet } from 'react-helmet-async'

const CulturalMap = lazy(() => import('../components/map/CulturalMap'))

class MapErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  state = { hasError: false }
  static getDerivedStateFromError() { return { hasError: true } }
  render() {
    if (this.state.hasError) {
      return (
        <div className="w-full h-[600px] border-2 border-black bg-gray-50 flex items-center justify-center">
          <div className="text-center px-8">
            <div className="text-4xl mb-4">🗺️</div>
            <p className="font-mono text-sm text-gray-600">No se pudo cargar el mapa</p>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

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
          <MapErrorBoundary>
            <Suspense fallback={
              <div className="w-full h-[600px] bg-gray-50 flex items-center justify-center">
                <p className="font-mono text-sm text-gray-400 animate-pulse">Cargando mapa…</p>
              </div>
            }>
              <CulturalMap />
            </Suspense>
          </MapErrorBoundary>
        </div>
      </div>
    </>
  )
}
