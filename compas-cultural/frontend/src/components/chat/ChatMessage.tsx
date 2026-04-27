import { Link } from 'react-router-dom'
import { type Evento, type Espacio } from '../../lib/api'
import { getEventDateParts } from '../../lib/datetime'
import SmartEventImage from '../ui/SmartEventImage'

function stripMarkdown(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, '')
    .replace(/#{1,6}\s+/g, '')
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\*(.+?)\*/g, '$1')
    .replace(/`(.+?)`/g, '$1')
    .replace(/\[(.+?)\]\(.+?\)/g, '$1')
    .replace(/^[-*+]\s+/gm, '· ')
    .replace(/^\d+\.\s+/gm, '')
    .replace(/^>\s+/gm, '')
    .replace(/---/g, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

interface Mensaje {
  id: string
  rol: 'usuario' | 'compas'
  contenido: string
  timestamp: string
}

interface ChatMessageProps {
  mensaje: Mensaje
  eventos?: Evento[]
  espacios?: Espacio[]
}

export default function ChatMessage({ mensaje, eventos, espacios }: ChatMessageProps) {
  const isUsuario = mensaje.rol === 'usuario'

  return (
    <div className={`flex ${isUsuario ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[85%] text-sm font-mono ${
        isUsuario
          ? 'bg-black text-white p-3'
          : 'bg-white text-black border-2 border-black'
      }`}>
        {/* Event mini-cards for AI responses */}
        {!isUsuario && eventos && eventos.length > 0 && (
          <div className="space-y-1 p-2 pb-0">
            {eventos.map((ev) => {
              const { diaCorto: dia, hora } = getEventDateParts(ev)
              const horaConfiable = ev.hora_confirmada === true && hora
              const horario = horaConfiable
                ? `${dia} · ${hora}`
                : `${dia} · Horario en el enlace`
              return (
                <Link
                  key={ev.id}
                  to={`/evento/${ev.slug}`}
                  className="flex gap-2 p-1.5 border border-black hover:bg-black hover:text-white transition-all duration-200"
                >
                  {ev.imagen_url && (
                    <div className="w-12 h-12 flex-shrink-0 overflow-hidden border-r border-black">
                      <SmartEventImage
                        primaryUrl={ev.imagen_url}
                        sourceUrl={ev.fuente_url}
                        alt={ev.titulo}
                        kind="thumb"
                        className="w-full h-full object-cover"
                        fallbackClassName="w-full h-full bg-black/10"
                      />
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1 mb-0.5">
                      <span className="text-[8px] font-bold uppercase tracking-wider border border-current px-1 leading-relaxed">
                        {ev.categoria_principal.replaceAll('_', ' ')}
                      </span>
                      {ev.es_gratuito && (
                        <span className="text-[8px] font-bold uppercase border border-current px-1 leading-relaxed">
                          Gratis
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] font-black uppercase leading-snug truncate">{ev.titulo}</p>
                    <p className="text-[9px] opacity-60">{horario}</p>
                  </div>
                </Link>
              )
            })}
          </div>
        )}

        {/* Espacio mini-cards for AI responses */}
        {!isUsuario && espacios && espacios.length > 0 && (
          <div className="space-y-1 p-2 pb-0">
            {espacios.map((esp) => (
              <Link
                key={esp.id}
                to={`/espacio/${esp.slug}`}
                className="flex items-center gap-2 p-1.5 border border-black hover:bg-black hover:text-white transition-all duration-200"
              >
                <span className="w-2 h-2 bg-current flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-[11px] font-black uppercase leading-snug truncate">{esp.nombre}</p>
                  <p className="text-[9px] opacity-60">{esp.categoria_principal.replaceAll('_', ' ')} · {esp.barrio ?? esp.municipio}</p>
                </div>
                <span className="text-[9px] opacity-50">→</span>
              </Link>
            ))}
          </div>
        )}

        {/* Text content */}
        <div className={!isUsuario ? 'p-3' : ''}>
          <span className="whitespace-pre-line">
            {isUsuario ? mensaje.contenido : stripMarkdown(mensaje.contenido)}
          </span>
        </div>
      </div>
    </div>
  )
}
