import { useState } from 'react'
import { Link } from 'react-router-dom'
import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'
import IcosaedroEterea from './IcosaedroEterea'
import { enviarMensajeChat, getEvento, getEspacio, type ChatMessage as ApiChatMessage, type Evento, type Espacio } from '../../lib/api'

interface Mensaje {
  id: string
  rol: 'usuario' | 'compas'
  contenido: string
  timestamp: string
  eventos?: Evento[]
  espacios?: Espacio[]
}

export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false)
  const [encima, setEncima] = useState(false)
  const [mensajes, setMensajes] = useState<Mensaje[]>([
    {
      id: '1',
      rol: 'compas',
      contenido: 'Hola, soy ETÉREA, tu asistente cultural del Valle de Aburrá. ¿Qué querés descubrir hoy?',
      timestamp: new Date().toISOString()
    }
  ])

  const toggleChat = () => setIsOpen(!isOpen)

  const construirHistorial = (mensajesActuales: Mensaje[]): ApiChatMessage[] => {
    return mensajesActuales.map((m) => ({
      rol: m.rol,
      contenido: m.contenido,
      timestamp: m.timestamp
    }))
  }

  const enviarMensaje = async (mensaje: string) => {
    const nuevoMensaje: Mensaje = {
      id: Date.now().toString(),
      rol: 'usuario',
      contenido: mensaje,
      timestamp: new Date().toISOString()
    }
    setMensajes(prev => [...prev, nuevoMensaje])

    try {
      const historial = construirHistorial(mensajes)
      const response = await enviarMensajeChat(mensaje, historial)

      // Fetch event data for fuentes of type 'evento'
      let eventosData: Evento[] = []
      const eventoFuentes = response.fuentes.filter(f => f.tipo === 'evento')
      if (eventoFuentes.length > 0) {
        const fetched = await Promise.allSettled(
          eventoFuentes.map(f => getEvento(f.nombre))
        )
        eventosData = fetched
          .filter((r): r is PromiseFulfilledResult<Evento> => r.status === 'fulfilled')
          .map(r => r.value)
      }

      // Fetch espacio data for fuentes of type 'espacio'
      let espaciosData: Espacio[] = []
      const espacioFuentes = response.fuentes.filter(f => f.tipo === 'espacio')
      if (espacioFuentes.length > 0) {
        const fetched = await Promise.allSettled(
          espacioFuentes.map(f => getEspacio(f.nombre))
        )
        espaciosData = fetched
          .filter((r): r is PromiseFulfilledResult<Espacio> => r.status === 'fulfilled')
          .map(r => r.value)
      }

      const respuesta: Mensaje = {
        id: (Date.now() + 1).toString(),
        rol: 'compas',
        contenido: response.respuesta,
        timestamp: new Date().toISOString(),
        eventos: eventosData.length > 0 ? eventosData : undefined,
        espacios: espaciosData.length > 0 ? espaciosData : undefined,
      }
      setMensajes(prev => [...prev, respuesta])
    } catch {
      const fallback: Mensaje = {
        id: (Date.now() + 1).toString(),
        rol: 'compas',
        contenido: 'No pude consultar datos en vivo. Intenta de nuevo en un momento.',
        timestamp: new Date().toISOString()
      }
      setMensajes(prev => [...prev, fallback])
    }
  }

  if (!isOpen) {
    return (
      <div className="fixed bottom-20 right-3 md:bottom-8 md:right-6 z-[60]">
        <button
          onClick={toggleChat}
          onMouseEnter={() => setEncima(true)}
          onMouseLeave={() => setEncima(false)}
          onFocus={() => setEncima(true)}
          onBlur={() => setEncima(false)}
          aria-label="Abrir ETÉREA, la IA de la agenda cultural"
          title="Pregúntale a ETÉREA"
          className="group flex flex-col items-center gap-0.5 px-1.5 pt-1.5 pb-1 bg-black text-white border-2 border-black hover:bg-white hover:text-black focus-visible:bg-white focus-visible:text-black transition-colors shadow-[4px_4px_0_0_rgba(0,0,0,0.3)]"
        >
          <IcosaedroEterea size={42} velocidad={encima ? 2.6 : 1} />
          <span className="flex items-center gap-1 font-mono text-[10px] font-bold tracking-[0.18em] leading-none">
            ETÉREA
            <span className="px-1 py-0.5 bg-white text-black group-hover:bg-black group-hover:text-white group-focus-visible:bg-black group-focus-visible:text-white text-[9px] tracking-normal">IA</span>
          </span>
        </button>
      </div>
    )
  }

  return (
    <div className="fixed bottom-20 md:bottom-8 right-3 md:right-6 w-[calc(100vw-1.5rem)] max-w-80 h-[28rem] bg-white border-2 border-black z-[60] flex flex-col shadow-[8px_8px_0px_0px_rgba(0,0,0,1)]">
      <div className="px-4 py-3 border-b-2 border-black flex justify-between items-center bg-black text-white">
        <div className="flex items-center gap-2">
          <IcosaedroEterea size={28} nube={false} />
          <div className="leading-tight">
            <h3 className="font-mono font-bold text-[11px] tracking-[0.2em] uppercase">ETÉREA</h3>
            <p className="font-mono text-[9px] tracking-wider opacity-70">IA de la agenda cultural</p>
          </div>
        </div>
        <button onClick={toggleChat} className="text-white hover:opacity-60 transition-opacity text-lg font-black">
          ✕
        </button>
      </div>

      <div className="flex-1 p-4 space-y-3 overflow-y-auto">
        {mensajes.map((mensaje) => (
          <ChatMessage key={mensaje.id} mensaje={mensaje} eventos={mensaje.eventos} espacios={mensaje.espacios} />
        ))}
      </div>

      <div className="border-t-2 border-black">
        <ChatInput onSend={enviarMensaje} />
        <Link
          to="/chat"
          className="block text-center text-[10px] font-mono font-bold uppercase tracking-wider text-black py-2 hover:bg-black hover:text-white transition-all duration-200 border-t-2 border-black"
          onClick={toggleChat}
        >
          Abrir chat completo
        </Link>
      </div>
    </div>
  )
}
