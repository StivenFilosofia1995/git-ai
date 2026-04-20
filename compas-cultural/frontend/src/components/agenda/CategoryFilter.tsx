interface CategoryFilterProps {
  categoriasSeleccionadas: string[]
  onCategoriaToggle: (categoria: string) => void
}

export default function CategoryFilter({ categoriasSeleccionadas, onCategoriaToggle }: Readonly<CategoryFilterProps>) {
  const categorias = [
    'teatro', 'rock', 'hip_hop', 'jazz', 'musica_en_vivo', 'electronica',
    'galeria', 'arte_contemporaneo', 'libreria', 'poesia',
    'filosofia', 'cine', 'danza', 'festival', 'fotografia',
    'taller', 'conferencia',
  ]

  return (
    <div className="flex flex-wrap gap-2">
      {categorias.map((categoria) => (
        <button
          key={categoria}
          onClick={() => onCategoriaToggle(categoria)}
          className={`px-3 py-1 text-xs font-mono uppercase border ${
            categoriasSeleccionadas.includes(categoria)
              ? 'border-black bg-black text-white'
              : 'border-black hover:bg-black hover:text-white'
          } transition-colors`}
        >
          {categoria.replace('_', ' ')}
        </button>
      ))}
    </div>
  )
}