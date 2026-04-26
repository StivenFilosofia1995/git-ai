import { getEventDateParts } from '../../lib/datetime'

interface EventDetailProps {
  evento: {
    titulo: string
    descripcion?: string
    fecha_inicio: string
    fuente?: string | null
    hora_confirmada?: boolean | null
    categoria_principal: string
    barrio: string
    nombre_lugar?: string
    precio?: string
  }
}

export default function EventDetail({ evento }: Readonly<EventDetailProps>) {
  const { diaLargo: fechaFormateada, hora } = getEventDateParts(evento)
  const horaConfirmada = evento.hora_confirmada === true && hora
  const horaLabel = horaConfirmada ? hora : null

  return (
    <div className="border-2 border-black p-6">
      <h2 className="text-xl font-bold mb-2">{evento.titulo}</h2>
      <p className="mb-4">{evento.descripcion}</p>

      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <span className="font-mono font-bold">FECHA</span>
          <p className="capitalize">{fechaFormateada}</p>
          {horaLabel
            ? <p>{horaLabel}</p>
            : <p className="text-xs opacity-60">Horario en el enlace del evento</p>
          }
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