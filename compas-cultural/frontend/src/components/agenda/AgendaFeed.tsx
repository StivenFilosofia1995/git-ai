import { useEffect, useState } from 'react'
import EventCard from './EventCard'
import { getEventosHoy, getEventos, type Evento } from '../../lib/api'

export default function AgendaFeed() {
  const [eventos, setEventos] = useState<Evento[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [label, setLabel] = useState('HOY')

  useEffect(() => {
    const inicializarAgenda = async () => {
      try {
        const hoy = await getEventosHoy()
        if (hoy.length > 0) {
          setEventos(hoy)
          setLabel('HOY')
        } else {
          const proximos = await getEventos({ limit: 6 })
          setEventos(proximos)
          setLabel('PRÓXIMOS')
        }
      } catch {
        setError('No fue posible cargar la agenda.')
      } finally {
        setLoading(false)
      }
    }

    void inicializarAgenda()
  }, [])

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map(i => (
          <div key={i} className="animate-pulse border-2 border-black p-4">
            <div className="h-3 bg-black/10 w-16 mb-2" />
            <div className="h-4 bg-black/10 w-3/4 mb-2" />
            <div className="h-3 bg-black/5 w-1/2" />
          </div>
        ))}
      </div>
    )
  }

  if (error) return <div className="text-sm text-black font-mono border-2 border-black p-4">{error}</div>

  return (
    <div>
      {label === 'PRÓXIMOS' && (
        <p className="text-[10px] font-mono font-bold mb-3 tracking-wider uppercase">
          No hay eventos hoy — mostrando próximos
        </p>
      )}
      <div className="space-y-3">
        {eventos.length === 0 ? (
          <p className="text-sm font-mono p-4 border-2 border-black">No hay eventos próximos programados.</p>
        ) : (
          eventos.map((evento) => (
            <EventCard key={evento.id} evento={evento} compact />
          ))
        )}
      </div>
    </div>
  )
}