import { getEventDateParts } from '../../lib/datetime'

interface EventDetailProps {
  evento: {
    titulo: string
    descripcion?: string
    fecha_inicio: string
    categoria_principal: string
    barrio: string
    nombre_lugar?: string
    precio?: string
  }
}

export default function EventDetail({ evento }: Readonly<EventDetailProps>) {
  const { diaLargo: fechaFormateada, hora } = getEventDateParts(evento.fecha_inicio)
  const horaLabel = hora ?? 'Hora por confirmar'

  return (
    <div className="border-2 border-black p-6">
      <h2 className="text-xl font-bold mb-2">{evento.titulo}</h2>
      <p className="mb-4">{evento.descripcion}</p>

      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <span className="font-mono font-bold">FECHA</span>
          <p className="capitalize">{fechaFormateada}</p>
          <p>{horaLabel}</p>
        </div>
        <div>
          <span className="font-mono font-bold">LUGAR</span>
          <p>{evento.nombre_lugar || evento.barrio}</p>
        </div>
        <div>
          <span className="font-mono font-bold">CATEGORÍA</span>
          <p>{evento.categoria_principal}</p>
        </div>
        {evento.precio && (
          <div>
            <span className="font-mono font-bold">PRECIO</span>
            <p>{evento.precio}</p>
          </div>
        )}
      </div>
    </div>
  )
}