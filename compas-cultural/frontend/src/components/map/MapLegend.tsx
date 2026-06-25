export default function MapLegend() {
  const categorias = [
    { nombre: 'Teatro', color: 'bg-teatro' },
    { nombre: 'Hip Hop', color: 'bg-hip-hop' },
    { nombre: 'Jazz', color: 'bg-jazz' },
    { nombre: 'Galerías', color: 'bg-galeria' },
    { nombre: 'Librerías', color: 'bg-libreria' },
    { nombre: 'Casas de Cultura', color: 'bg-casa-cultura' },
    { nombre: 'Festivales', color: 'bg-festival' }
  ]

  return (
    <div className="bg-white border-2 border-black p-4">
      <h4 className="font-mono font-bold text-sm mb-3">LEYENDA</h4>
      <div className="space-y-2">
        {categorias.map((cat) => (
          <div key={cat.nombre} className="flex items-center space-x-2">
            <div className={`w-3 h-3 rounded-full ${cat.color}`} />
            <span className="text-xs">{cat.nombre}</span>
          </div>
        ))}
      </div>
    </div>
  )
}