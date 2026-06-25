import SpaceCard from './SpaceCard'
import { type Espacio } from '../../lib/api'

interface SpaceGridProps {
  espacios: Espacio[]
  loading?: boolean
}

export default function SpaceGrid({ espacios, loading }: Readonly<SpaceGridProps>) {
  if (loading) {
    const skeletonIds = ['s1', 's2', 's3', 's4', 's5', 's6']

    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {skeletonIds.map((skeletonId) => (
          <div key={skeletonId} className="border-2 border-black p-5 animate-pulse">
            <div className="h-4 bg-black/10 mb-2"></div>
            <div className="h-3 bg-black/10 mb-1"></div>
            <div className="h-3 bg-black/5"></div>
          </div>
        ))}
      </div>
    )
  }

  if (espacios.length === 0) {
    return (
      <div className="text-center py-8 border-2 border-black">
        <p className="font-mono text-sm uppercase tracking-wider">No se encontraron espacios.</p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {espacios.map((espacio) => (
        <SpaceCard key={espacio.id} espacio={espacio} />
      ))}
    </div>
  )
}