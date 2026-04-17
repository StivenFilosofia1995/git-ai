interface DateFilterProps {
  fechaSeleccionada: string
  onFechaChange: (fecha: string) => void
}

export default function DateFilter({ fechaSeleccionada, onFechaChange }: DateFilterProps) {
  const opciones = [
    { value: 'hoy', label: 'Hoy' },
    { value: 'mañana', label: 'Mañana' },
    { value: 'semana', label: 'Esta semana' },
    { value: 'mes', label: 'Este mes' }
  ]

  return (
    <div className="flex space-x-2">
      {opciones.map((opcion) => (
        <button
          key={opcion.value}
          onClick={() => onFechaChange(opcion.value)}
          className={`px-3 py-1 text-xs font-mono uppercase border ${
            fechaSeleccionada === opcion.value
              ? 'border-black bg-black text-white'
              : 'border-black hover:bg-black hover:text-white'
          } transition-colors`}
        >
          {opcion.label}
        </button>
      ))}
    </div>
  )
}