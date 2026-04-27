import { Helmet } from 'react-helmet-async'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { enviarMensajeChat, getEvento, getEspacio, type ChatMessage, type Evento, type Espacio } from '../lib/api'
import { getEventDateParts } from '../lib/datetime'
import EtereaThinking from '../components/chat/EtereaThinking'
import SmartEventImage from '../components/ui/SmartEventImage'

function stripMarkdown(text: string): string {
  return text
    .replaceAll(/```[\s\S]*?```/g, '')
    .replaceAll(/#{1,6}\s+/g, '')
    .replaceAll(/\*\*(.+?)\*\*/g, '$1')
    .replaceAll(/\*(.+?)\*/g, '$1')
    .replaceAll(/`(.+?)`/g, '$1')
    .replaceAll(/\[(.+?)\]\(.+?\)/g, '$1')
    .replaceAll(/^[-*+]\s+/gm, '· ')
    .replaceAll(/^\d+\.\s+/gm, '')
    .replaceAll(/^>\s+/gm, '')
    .replaceAll('---', '')
    .replaceAll(/\n{3,}/g, '\n\n')
    .trim()
}

interface Mensaje {
  id: string
  rol: 'usuario' | 'compas'
  contenido: string
  timestamp: string
  eventos?: Evento[]
  espacios?: Espacio[]
}

function normalizePrompt(text: string): string {
  return text.toLowerCase().normalize('NFD').replaceAll(/[\u0300-\u036f]/g, '').trim()
}

function shouldShowStructuredResults(text: string): boolean {
  const t = normalizePrompt(text)
  return [
    'evento', 'eventos', 'hoy', 'semana', 'fin de semana', 'plan', 'planes',
    'teatro', 'jazz', 'hip hop', 'hiphop', 'galeria', 'galerias', 'cine', 'danza',
    'gratis', 'musica', 'música', 'libreria', 'librerias', 'donde', 'recomienda',
  ].some(token => t.includes(token))
}

export default function Chat() {
  const [searchParams] = useSearchParams()
  const [mensajes, setMensajes] = useState<Mensaje[]>([
    {
      id: '1',
      rol: 'compas',
      contenido: 'Hola, soy ETÉREA, tu guía cultural del Valle de Aburrá. ¿En qué puedo ayudarte?',
      timestamp: new Date().toISOString()
    }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const q = searchParams.get('q')
    if (q) {
      setInput(q)
    }
  }, [searchParams])

  const construirHistorial = (mensajesActuales: Mensaje[]): ChatMessage[] => {
    return mensajesActuales.map((m) => ({
      rol: m.rol,
      contenido: m.contenido,
      timestamp: m.timestamp
    }))
  }

  const enviarMensaje = async () => {
    if (!input.trim()) return

    const nuevoMensaje: Mensaje = {
      id: Date.now().toString(),
      rol: 'usuario',
      contenido: input,
      timestamp: new Date().toISOString()
    }

    setMensajes(prev => [...prev, nuevoMensaje])
    setInput('')
    setLoading(true)
    setError(null)

    try {
      const historial = construirHistorial(mensajes)
      const response = await enviarMensajeChat(nuevoMensaje.contenido, historial)
      const showStructured = shouldShowStructuredResults(nuevoMensaje.contenido)

      // Fetch event details for fuentes
      let eventosData: Evento[] = []
      const eventoFuentes = response.fuentes.filter(f => f.tipo === 'evento')
      if (showStructured && eventoFuentes.length > 0) {
        const fetched = await Promise.allSettled(
          eventoFuentes.map(f => getEvento(f.nombre))
        )
        eventosData = fetched
          .filter((r): r is PromiseFulfilledResult<Evento> => r.status === 'fulfilled')
          .map(r => r.value)
      }

      // Fetch espacio details for fuentes
      let espaciosData: Espacio[] = []
      const espacioFuentes = response.fuentes.filter(f => f.tipo === 'espacio')
      if (showStructured && espacioFuentes.length > 0) {
        const fetched = await Promise.allSettled(
          espacioFuentes.map(f => getEspacio(f.nombre))
        )
        espaciosData = fetched
          .filter((r): r is PromiseFulfilledResult<Espacio> => r.status === 'fulfilled')
          .map(r => r.value)
      }

      const respuestaCompas: Mensaje = {
        id: (Date.now() + 1).toString(),
        rol: 'compas',
        contenido: response.respuesta,
        timestamp: new Date().toISOString(),
        eventos: eventosData.length > 0 ? eventosData : undefined,
        espacios: espaciosData.length > 0 ? espaciosData : undefined,
      }
      setMensajes(prev => [...prev, respuestaCompas])
    } catch {
      setError('No se pudo consultar el asistente en este momento.')
      const fallback: Mensaje = {
        id: (Date.now() + 1).toString(),
        rol: 'compas',
        contenido: 'Ahora mismo no puedo responder con datos en vivo. Intenta nuevamente en unos minutos.',
        timestamp: new Date().toISOString()
      }
      setMensajes(prev => [...prev, fallback])
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <Helmet>
        <title>Chat Cultural — Cultura ETÉREA</title>
      </Helmet>

      <div className="min-h-screen bg-white">
        <div className="max-w-4xl mx-auto px-4 py-8">
          <h1 className="text-3xl font-mono font-bold mb-8">CULTURA ETÉREA · CHAT</h1>

          <div className="border-2 border-black p-6 min-h-[600px] flex flex-col">
            <div className="flex-1 space-y-4 mb-6 overflow-y-auto">
              {error ? <p className="text-sm font-mono border-2 border-black p-2">{error}</p> : null}
              {mensajes.map((mensaje) => (
                <div key={mensaje.id} className={`flex ${mensaje.rol === 'usuario' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[70%] ${
                    mensaje.rol === 'usuario'
                      ? 'bg-black text-white p-4'
                      : 'bg-white border-2 border-black'
                  }`}>
                    {/* Event cards for AI responses */}
                    {mensaje.rol === 'compas' && mensaje.eventos && mensaje.eventos.length > 0 && (
                      <div className="space-y-2 p-3 pb-0">
                        {mensaje.eventos.map((ev) => {
                          const { diaCorto: dia, hora } = getEventDateParts(ev)
                          const horaConfiable = ev.hora_confirmada === true && hora
                          const horario = horaConfiable
                            ? `${dia} · ${hora}`
                            : `${dia} · Horario en el enlace`
                          return (
                            <Link
                              key={ev.id}
                              to={`/evento/${ev.slug}`}
                              className="group flex gap-3 border-2 border-black hover:bg-black hover:text-white transition-all duration-200"
                            >
                              {ev.imagen_url && (
                                <div className="w-24 h-24 flex-shrink-0 overflow-hidden border-r-2 border-black">
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
                              <div className="py-2 pr-3 flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-1">
                                  <span className="text-[9px] font-mono font-bold uppercase tracking-wider border border-current px-1.5 py-0.5 leading-none">
                                    {ev.categoria_principal.replaceAll('_', ' ')}
                                  </span>
                                  {ev.es_gratuito && (
                                    <span className="text-[9px] font-mono font-bold uppercase tracking-wider border border-current px-1.5 py-0.5 leading-none">
                                      Gratis
                                    </span>
                                  )}
                                </div>
                                <h4 className="text-sm font-heading font-black uppercase tracking-wide leading-snug">
                                  {ev.titulo}
                                </h4>
                                <div className="flex items-center gap-1.5 mt-1 text-[11px] font-mono opacity-70">
                                  <span>{horario}</span>
                                  {ev.nombre_lugar && <span>· {ev.nombre_lugar}</span>}
                                </div>
                                {ev.precio && (
                                  <p className="text-[10px] font-mono mt-1 opacity-60">{ev.precio}</p>
                                )}
                              </div>
                            </Link>
                          )
                        })}
                      </div>
                    )}

                    {/* Espacio cards for AI responses */}
                    {mensaje.rol === 'compas' && mensaje.espacios && mensaje.espacios.length > 0 && (
                      <div className="space-y-2 p-3 pb-0">
                        {mensaje.espacios.map((esp) => (
                          <Link
                            key={esp.id}
                            to={`/espacio/${esp.slug}`}
                            className="group flex items-center gap-3 border-2 border-black p-3 hover:bg-black hover:text-white transition-all duration-200"
                          >
                            <span className="w-3 h-3 bg-current flex-shrink-0" />
                            <div className="flex-1 min-w-0">
                              <h4 className="text-sm font-heading font-black uppercase tracking-wide leading-snug truncate">
                                {esp.nombre}
                              </h4>
                              <div className="flex items-center gap-1.5 mt-0.5 text-[11px] font-mono opacity-70">
                                <span>{esp.categoria_principal.replaceAll('_', ' ')}</span>
                                {esp.barrio && <span>· {esp.barrio}</span>}
                              </div>
                            </div>
                            <span className="text-sm opacity-40 group-hover:opacity-100">→</span>
                          </Link>
                        ))}
                      </div>
                    )}

                    {/* Text content (markdown stripped for AI) */}
                    <p className="text-sm font-mono whitespace-pre-line p-4">
                      {mensaje.rol === 'usuario' ? mensaje.contenido : stripMarkdown(mensaje.contenido)}
                    </p>
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex justify-start">
                  <EtereaThinking />
                </div>
              )}
            </div>

            <div className="flex gap-0">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && enviarMensaje()}
                placeholder="Escribe tu pregunta cultural..."
                className="flex-1 px-4 py-3 border-2 border-black focus:outline-none font-mono text-sm"
                disabled={loading}
              />
              <button
                onClick={enviarMensaje}
                disabled={loading || !input.trim()}
                className="bg-black text-white px-6 py-3 font-mono font-bold text-sm uppercase tracking-wider border-2 border-black -ml-[2px] hover:bg-white hover:text-black transition-all disabled:opacity-50"
              >
                ENVIAR
              </button>
            </div>
          </div>

          <div className="mt-8">
            <h3 className="font-mono font-bold mb-4">PREGUNTAS SUGERIDAS</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {[
                '¿Qué hay hoy en el centro?',
                'Eventos de jazz esta semana',
                'Dónde ver teatro independiente',
                'Freestyle rap esta noche',
                'Librerías cerca de Laureles',
                'Arte contemporáneo en El Poblado'
              ].map((pregunta) => (
                <button
                  key={pregunta}
                  onClick={() => setInput(pregunta)}
                  className="text-left p-4 border-2 border-black hover:bg-black hover:text-white transition-all duration-300"
                >
                  <span className="text-sm font-mono">{pregunta}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
