interface MapFiltersProps {
  categorias: string[]
  onCategoriaToggle: (categoria: string) => void
}

export default function MapFilters({ categorias, onCategoriaToggle }: Readonly<MapFiltersProps>) {
  const categoriasDisponibles = [
    'teatro', 'hip-hop', 'jazz', 'galeria', 'libreria', 'casa-cultura', 'festival'
  ]

  return (
    <div className="space-y-2">
      {categoriasDisponibles.map((categoria) => (
        <label key={categoria} className="flex items-center space-x-2 text-xs cursor-pointer">
          <input
            type="checkbox"
            checked={categorias.includes(categoria)}
            onChange={() => onCategoriaToggle(categoria)}
            className="rounded"
          />
          <span className="capitalize">{categoria.replace('-', ' ')}</span>
        </label>
      ))}
    </div>
  )
}