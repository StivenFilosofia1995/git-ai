import { useState, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { enviarMensajeChat, getEvento, getEspacio, getZonas, registrarBusqueda, type ChatMessage, type Evento, type Espacio, type Zona } from '../../lib/api'
import { useAuth } from '../../lib/AuthContext'
import { getEventDateParts } from '../../lib/datetime'
import EtereaThinking from './EtereaThinking'

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
  eventos?: Evento[]
  espacios?: Espacio[]
  enlaces?: Array<{ tipo: string; nombre: string; url?: string | null; instagram?: string | null; sitio_web?: string | null }>
}

const QUICK_ASKS = [
  '¿Qué hay hoy en Medellín?',
  'Eventos de jazz esta semana',
  'Teatro independiente hoy',
  'Freestyle rap esta noche',
  '¿Dónde hay galerías abiertas?',
  'Eventos gratis este fin de semana',
]

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

export default function HomeChatSection() {
  const { user } = useAuth()
  const [mensajes, setMensajes] = useState<Mensaje[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [zona, setZona] = useState('')
  const [zonas, setZonas] = useState<Zona[]>([])
  const [ubicacion, setUbicacion] = useState<{ lat: number; lng: number } | null>(null)
  const [geoLoading, setGeoLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    getZonas().then(setZonas).catch(() => {})
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [mensajes])

  const pedirUbicacion = () => {
    if (!navigator.geolocation) return
    setGeoLoading(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setUbicacion({ lat: pos.coords.latitude, lng: pos.coords.longitude })
        setGeoLoading(false)
      },
      () => setGeoLoading(false),
      { enableHighAccuracy: true, timeout: 8000 }
    )
  }

  const enviarMensaje = async (texto: string) => {
    if (!texto.trim() || loading) return
    setInput('')
    setLoading(true)

    // Add context prefix if zone/location selected
    let mensajeConContexto = texto
    if (zona) {
      mensajeConContexto = `[Zona: ${zona}] ${texto}`
    }
    if (ubicacion) {
      mensajeConContexto = `[Ubicación: ${ubicacion.lat}, ${ubicacion.lng}] ${mensajeConContexto}`
    }

    const nuevoMsg: Mensaje = { id: Date.now().toString(), rol: 'usuario', contenido: texto }
    setMensajes(prev => [...prev, nuevoMsg])

    try {
      const historial: ChatMessage[] = mensajes.slice(-6).map(m => ({
        rol: m.rol,
        contenido: m.contenido,
        timestamp: new Date().toISOString(),
      }))

      const res = await enviarMensajeChat(mensajeConContexto, historial)
      const showStructured = shouldShowStructuredResults(texto)

      // Fetch event details
      let eventosData: Evento[] = []
      const eventoFuentes = res.fuentes.filter(f => f.tipo === 'evento')
      if (showStructured && eventoFuentes.length > 0) {
        const fetched = await Promise.allSettled(eventoFuentes.map(f => getEvento(f.nombre)))
        eventosData = fetched
          .filter((r): r is PromiseFulfilledResult<Evento> => r.status === 'fulfilled')
          .map(r => r.value)
      }

      // Fetch espacio details
      let espaciosData: Espacio[] = []
      const espacioFuentes = res.fuentes.filter(f => f.tipo === 'espacio')
      if (showStructured && espacioFuentes.length > 0) {
        const fetched = await Promise.allSettled(espacioFuentes.map(f => getEspacio(f.nombre)))
        espaciosData = fetched
          .filter((r): r is PromiseFulfilledResult<Espacio> => r.status === 'fulfilled')
          .map(r => r.value)
      }

      // Build links from fuentes
      const enlaces = (showStructured ? res.fuentes : [])
        .filter(f => f.instagram || f.sitio_web)
        .map(f => ({ tipo: f.tipo, nombre: f.nombre, url: f.url, instagram: f.instagram, sitio_web: f.sitio_web }))

      const respuesta: Mensaje = {
        id: (Date.now() + 1).toString(),
        rol: 'compas',
        contenido: res.respuesta,
        eventos: eventosData.length > 0 ? eventosData : undefined,
        espacios: espaciosData.length > 0 ? espaciosData : undefined,
        enlaces: enlaces.length > 0 ? enlaces : undefined,
      }
      setMensajes(prev => [...prev, respuesta])

      // Track search for learning algorithm
      if (user) {
        const categorias = res.fuentes.map(f => f.categoria).filter(Boolean)
        registrarBusqueda(texto, [...new Set(categorias)], user.id).catch(() => {})
      }
    } catch {
      setMensajes(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        rol: 'compas',
        contenido: 'No pude consultar datos en este momento. Intentá de nuevo.',
      }])
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    void enviarMensaje(input)
  }

  return (
    <section className="py-16 border-t-2 border-black">
      <div className="flex items-center gap-3 mb-8">
        <span className="w-4 h-4 bg-black" />
        <h2 className="text-xl font-heading font-black uppercase tracking-wider">
          Preguntale a ETÉREA
        </h2>
        <span className="w-2 h-2 bg-black animate-pulse ml-1" />
      </div>

      <div className="border-2 border-black bg-white">
        {/* Location/Zone bar */}
        <div className="flex items-center gap-3 px-4 py-3 border-b-2 border-black bg-black/[0.02] flex-wrap">
          <span className="text-[9px] font-mono font-bold uppercase tracking-wider opacity-40">🔍 Filtrá tu búsqueda:</span>

          {/* Zone selector */}
          <select
            value={zona}
            onChange={(e) => setZona(e.target.value)}
            className="text-[11px] font-mono font-bold border-2 border-black px-2 py-1 bg-white uppercase tracking-wider focus:outline-none"
          >
            <option value="">📍 Toda la ciudad</option>
            {zonas.map(z => (
              <option key={z.id} value={z.nombre}>◉ {z.nombre}</option>
            ))}
          </select>

          {/* Geolocation button */}
          <button
            onClick={pedirUbicacion}
            disabled={geoLoading}
            className={`inline-flex items-center gap-1.5 px-2 py-1 text-[11px] font-mono font-bold uppercase tracking-wider border-2 border-black transition-all duration-200 ${
              ubicacion ? 'bg-black text-white' : 'hover:bg-black hover:text-white'
            }`}
            title="Activá tu ubicación para resultados cerca de vos"
          >
            {geoLoading ? (
              <div className="w-3 h-3 border border-current border-t-transparent animate-spin" />
            ) : (
              <span className="text-xs">◎</span>
            )}
            {ubicacion ? 'Cerca de mí ✓' : 'Usar mi ubicación'}
          </button>

          {ubicacion && (
            <button
              onClick={() => setUbicacion(null)}
              className="text-[10px] font-mono opacity-40 hover:opacity-100"
            >
              ✕
            </button>
          )}

          {(zona || ubicacion) && (
            <span className="text-[9px] font-mono text-green-700 font-bold">
              ✓ Resultados filtrados por {zona ? `zona "${zona}"` : ''}{zona && ubicacion ? ' y ' : ''}{ubicacion ? 'tu ubicación' : ''}
            </span>
          )}
        </div>

        {/* Chat messages */}
        <div className="min-h-[120px] max-h-[460px] overflow-y-auto p-4 space-y-3">
          {mensajes.length === 0 ? (
            <div>
              <p className="text-sm font-mono opacity-60 mb-2">
                🔍 Buscá eventos, espacios, artistas y más en el Valle de Aburrá.
              </p>
              <p className="text-[11px] font-mono opacity-40 mb-4">
                Podés seleccionar tu zona arriba o activar tu ubicación para resultados cercanos. ETÉREA busca en toda la base de datos cultural.
              </p>
              <div className="flex flex-wrap gap-2">
                {QUICK_ASKS.map(q => (
                  <button
                    key={q}
                    onClick={() => void enviarMensaje(q)}
                    className="text-[11px] font-mono px-3 py-2 border-2 border-black hover:bg-black hover:text-white transition-all duration-200"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {mensajes.map(msg => (
                <div key={msg.id} className={`flex ${msg.rol === 'usuario' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[85%] ${
                    msg.rol === 'usuario'
                      ? 'bg-black text-white p-3'
                      : 'border-2 border-black'
                  }`}>
                    {/* Event cards */}
                    {msg.eventos && msg.eventos.length > 0 && (
                      <div className="space-y-1.5 p-3 pb-0">
                        {msg.eventos.map(ev => {
                          const { diaCorto: dia, hora } = getEventDateParts(ev)
                          const horaConfiable = ev.hora_confirmada === true && hora
                          const horario = horaConfiable
                            ? `${dia} · ${hora}`
                            : `${dia} · ${ev.fuente_url ? 'Horario en el enlace' : 'Horario por confirmar'}`
                          return (
                            <Link
                              key={ev.id}
                              to={`/evento/${ev.slug}`}
                              className="group flex gap-2 border border-black hover:bg-black hover:text-white transition-all duration-200"
                            >
                              {ev.imagen_url && (
                                <div className="w-16 h-16 flex-shrink-0 overflow-hidden border-r border-black">
                                  <img src={ev.imagen_url} alt={ev.titulo} className="w-full h-full object-cover" loading="lazy" />
                                </div>
                              )}
                              <div className="py-1.5 pr-2 flex-1 min-w-0">
                                <div className="flex items-center gap-1 mb-0.5">
                                  <span className="text-[8px] font-mono font-bold uppercase tracking-wider border border-current px-1 leading-relaxed">
                                    {ev.categoria_principal.replaceAll('_', ' ')}
                                  </span>
                                  {ev.es_gratuito && (
                                    <span className="text-[8px] font-mono font-bold uppercase border border-current px-1 leading-relaxed">
                                      Gratis
                                    </span>
                                  )}
                                </div>
                                <p className="text-[11px] font-heading font-black uppercase leading-snug truncate">{ev.titulo}</p>
                                <p className="text-[9px] font-mono opacity-60">{horario}{ev.nombre_lugar ? ` · ${ev.nombre_lugar}` : ''}</p>
                              </div>
                            </Link>
                          )
                        })}
                      </div>
                    )}

                    {/* Espacio cards */}
                    {msg.espacios && msg.espacios.length > 0 && (
                      <div className="space-y-1 p-3 pb-0">
                        {msg.espacios.map(esp => (
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

                    {/* External links (Instagram, websites) */}
                    {msg.enlaces && msg.enlaces.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 px-3 pt-2">
                        {msg.enlaces.map((enlace) => (
                          <span key={`${enlace.tipo}-${enlace.nombre}-${enlace.instagram ?? enlace.sitio_web ?? 'link'}`} className="inline-flex items-center gap-1">
                            {enlace.instagram && (
                              <a
                                href={`https://instagram.com/${enlace.instagram.replace('@', '')}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-[9px] font-mono px-1.5 py-0.5 border border-black/30 hover:bg-black hover:text-white transition-all"
                              >
                                @{enlace.instagram.replace('@', '')}
                              </a>
                            )}
                            {enlace.sitio_web && (
                              <a
                                href={enlace.sitio_web.startsWith('http') ? enlace.sitio_web : `https://${enlace.sitio_web}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-[9px] font-mono px-1.5 py-0.5 border border-black/30 hover:bg-black hover:text-white transition-all"
                              >
                                🌐 Web
                              </a>
                            )}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Text */}
                    <p className={`text-sm font-mono whitespace-pre-line ${msg.rol === 'compas' ? 'p-3' : ''}`}>
                      {msg.rol === 'usuario' ? msg.contenido : stripMarkdown(msg.contenido)}
                    </p>
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex justify-start">
                  <EtereaThinking compact />
                </div>
              )}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* Input bar */}
        <form onSubmit={handleSubmit} className="flex border-t-2 border-black">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="¿Qué querés descubrir hoy?"
            className="flex-1 px-4 py-3.5 text-sm font-mono focus:outline-none placeholder:text-black/30"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="px-6 bg-black text-white text-[11px] font-mono font-bold uppercase tracking-wider border-l-2 border-black hover:bg-white hover:text-black transition-all duration-300 disabled:opacity-20"
          >
            {loading ? '...' : 'ENVIAR'}
          </button>
        </form>

        {/* Expandir */}
        <Link
          to="/chat"
          className="block text-center text-[10px] font-mono font-bold uppercase tracking-wider py-2.5 border-t-2 border-black hover:bg-black hover:text-white transition-all duration-200"
        >
          Abrir chat completo →
        </Link>
      </div>
    </section>
  )
}
