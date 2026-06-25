interface MapMarkerProps {
  categoria: string
  nombre: string
  onClick?: () => void
}

export default function MapMarker({ categoria, nombre, onClick }: Readonly<MapMarkerProps>) {
  const getColor = (cat: string) => {
    const colors: Record<string, string> = {
      'teatro': 'bg-teatro',
      'hip-hop': 'bg-hip-hop',
      'jazz': 'bg-jazz',
      'galeria': 'bg-galeria',
      'libreria': 'bg-libreria',
      'casa-cultura': 'bg-casa-cultura'
    }
    return colors[cat.toLowerCase()] || 'bg-black'
  }

  return (
    <button
      type="button"
      className={`w-6 h-6 rounded-full border-2 border-white ${getColor(categoria)} cursor-pointer hover:scale-110 transition-transform`}
      onClick={onClick}
      title={nombre}
      aria-label={`Ver ${nombre}`}
    />
  )
}