import { Link } from 'react-router-dom'
import { useEffect, useRef } from 'react'
import { type Evento, trackInteraccion } from '../../lib/api'
import { getEventDateParts } from '../../lib/datetime'
import SmartEventImage from '../ui/SmartEventImage'
import { useAuth } from '../../lib/AuthContext'

interface EventCardProps {
  evento: Evento
  compact?: boolean
}

const CAT_COLORS: Record<string, string> = {
  teatro: '#DC2626',
  rock: '#1a1a1a',
  hip_hop: '#F59E0B',
  jazz: '#7C3AED',
  galeria: '#EC4899',
  arte_contemporaneo: '#EC4899',
  libreria: '#10B981',
  casa_cultura: '#3B82F6',
  electronica: '#06B6D4',
  danza: '#F97316',
  musica_en_vivo: '#06B6D4',
  batalla_freestyle: '#F59E0B',
  poesia: '#8B5CF6',
  festival: '#F97316',
  cine: '#6B7280',
  fotografia: '#7C3AED',
  muralismo: '#F59E0B',
  filosofia: '#1E40AF',
  taller: '#059669',
  conferencia: '#4338CA',
}

export default function EventCard({ evento, compact }: Readonly<EventCardProps>) {
  const { user } = useAuth()
  const cardRef = useRef<HTMLDivElement>(null)
  const viewTracked = useRef(false)

  const { diaCorto: dia, hora } = getEventDateParts(evento)
  const cat = evento.categoria_principal
  const placeholderColor = CAT_COLORS[cat] ?? '#0a0a0a'
  const horaConfirmada = evento.hora_confirmada === true && hora
  const fechaLabel = horaConfirmada ? `${dia} · ${hora}` : dia
  const horaPrompt = horaConfirmada ? hora : 'Horario en el enlace'

  const sourceUrl = evento.fuente_url || null
  const isIg = evento.fuente?.includes('instagram')
  const ubicacionLabel = [evento.nombre_lugar, evento.barrio, evento.municipio].filter(Boolean).join(', ')
  const mapsSearchTarget = ubicacionLabel || `${evento.titulo}, Medellin`
  const mapsUrl = evento.lat && evento.lng
    ? `https://www.google.com/maps?q=${evento.lat},${evento.lng}`
    : `https://www.google.com/maps/search/${encodeURIComponent(mapsSearchTarget)}`
  const preguntaEterea = encodeURIComponent(
    `Quiero que me cuentes mas detalles solo de este evento: "${evento.titulo}". No me listes otros eventos. Fecha: ${dia} ${horaPrompt}. Lugar: ${ubicacionLabel || 'Medellin'}.`
  )

  // ─── ML: Intersection Observer para trackear view cuando el card es visible ──
  // Registra view_evento solo 1 vez por montaje y solo si hay usuario logueado.
  // Usa threshold=0.5 para asegurar que el usuario realmente vio la card.
  useEffect(() => {
    if (!user || viewTracked.current) return
    const el = cardRef.current
    if (!el) return
    const observer = new IntersectionObserver(
      entries => {
        if (entries[0].isIntersecting && !viewTracked.current) {
          viewTracked.current = true
          void trackInteraccion('view_evento', evento.id, cat, user.id, {
            barrio: evento.barrio ?? undefined,
            municipio: evento.municipio ?? undefined,
          })
          observer.disconnect()
        }
      },
      { threshold: 0.5 }
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [user, evento.id, cat, evento.barrio, evento.municipio])

  // ─── ML: Handler de click para trackear interacción más fuerte ───────────
  const handleClick = () => {
    if (user) {
      void trackInteraccion('click', evento.id, cat, user.id, {
        barrio: evento.barrio ?? undefined,
        municipio: evento.municipio ?? undefined,
      })
    }
  }

  return (
    <div ref={cardRef} className="group bg-white border-2 border-black hover:bg-black hover:text-white transition-all duration-300 overflow-hidden hover-lift flex flex-col">
      {/* Image */}
      <Link to={`/evento/${evento.slug}`} onClick={handleClick}>
        {evento.imagen_url ? (
          <div className={`${compact ? 'aspect-[2/1]' : 'aspect-[16/9]'} overflow-hidden border-b-2 border-black`}>
            <SmartEventImage
              primaryUrl={evento.imagen_url}
              sourceUrl={evento.fuente_url}
              alt={evento.titulo}
              kind="card"
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500 group-hover:opacity-80"
              fallback={(
                <div
                  className="w-full h-full flex items-center justify-center relative overflow-hidden"
                  style={{ backgroundColor: placeholderColor }}
                >
                  <div className="absolute inset-0 opacity-10">
                    <div className="absolute inset-0" style={{
                      backgroundImage: 'repeating-linear-gradient(45deg, transparent, transparent 10px, rgba(255,255,255,0.1) 10px, rgba(255,255,255,0.1) 20px)'
                    }} />
                  </div>
                  <div className="text-center text-white relative z-10">
                    <span className="text-3xl block mb-1">◈</span>
                    <span className="text-[10px] font-mono font-bold uppercase tracking-widest">
                      {cat.replaceAll('_', ' ')}
                    </span>
                  </div>
                </div>
              )}
            />
          </div>
        ) : (
          <div
            className={`${compact ? 'aspect-[2/1]' : 'aspect-[16/9]'} border-b-2 border-black flex items-center justify-center relative overflow-hidden`}
            style={{ backgroundColor: placeholderColor }}
          >
            <div className="absolute inset-0 opacity-10">
              <div className="absolute inset-0" style={{
                backgroundImage: 'repeating-linear-gradient(45deg, transparent, transparent 10px, rgba(255,255,255,0.1) 10px, rgba(255,255,255,0.1) 20px)'
              }} />
            </div>
            <div className="text-center text-white relative z-10">
              <span className="text-3xl block mb-1">◈</span>
              <span className="text-[10px] font-mono font-bold uppercase tracking-widest">
                {cat.replaceAll('_', ' ')}
              </span>
            </div>
          </div>
        )}
      </Link>

      <div className="p-4 flex flex-col flex-1">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] font-mono font-bold uppercase tracking-wider border-2 border-current px-2 py-0.5">
            {cat.replaceAll('_', ' ')}
          </span>
          <span className="text-[10px] font-mono font-bold">{fechaLabel}</span>
        </div>
        {!horaConfirmada && sourceUrl && (
          <a
            href={sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            onClick={e => e.stopPropagation()}
            className="inline-flex items-center gap-1 text-[9px] font-mono font-bold uppercase tracking-wider opacity-70 hover:opacity-100 underline mb-2"
          >
            🕐 Horario en el enlace
          </a>
        )}
        {!horaConfirmada && !sourceUrl && (
          <span className="text-[9px] font-mono opacity-50 mb-2 block">🕐 Horario en el enlace</span>
        )}

        <Link to={`/evento/${evento.slug}`} onClick={handleClick}>
          <h3 className="font-heading font-black text-sm leading-snug mb-2 uppercase tracking-wide">
            {evento.titulo}
          </h3>
        </Link>

        {evento.descripcion && !compact && (
          <p className="text-[11px] font-mono leading-relaxed opacity-60 group-hover:opacity-80 line-clamp-2 mb-2">
            {evento.descripcion}
          </p>
        )}

        {/* Location */}
        <div className="flex items-center gap-1.5 text-[11px] font-mono mb-2">
          <span className="w-1.5 h-1.5 bg-current shrink-0" />
          <span className="truncate">{evento.nombre_lugar ?? evento.barrio ?? 'Medellín'}</span>
          {evento.barrio && evento.nombre_lugar && (
            <span className="opacity-50 shrink-0">&middot; {evento.barrio}</span>
          )}
        </div>

        {/* Price + tags */}
        <div className="flex items-center gap-2 flex-wrap">
          {evento.es_gratuito && (
            <span className="text-[9px] font-mono font-bold uppercase tracking-wider border border-current px-1.5 py-0.5">
              Gratis
            </span>
          )}
          {evento.precio && !evento.es_gratuito && (
            <span className="text-[9px] font-mono font-bold opacity-60">{evento.precio}</span>
          )}
        </div>

        {/* Actions — always at bottom */}
        <div className="mt-auto pt-3 flex items-center gap-3 flex-wrap border-t border-current/10">
          <Link
            to={`/chat?q=${preguntaEterea}`}
            className="text-[9px] font-mono font-bold uppercase tracking-wider opacity-70 hover:opacity-100 transition-opacity flex items-center gap-1"
          >
            🤖 <span className="underline">ETÉREA</span>
          </Link>
          <a
            href={mapsUrl}
            target="_blank"
            rel="noopener noreferrer"
            onClick={e => e.stopPropagation()}
            className="text-[9px] font-mono font-bold uppercase tracking-wider opacity-50 hover:opacity-100 transition-opacity flex items-center gap-1"
          >
            📍 <span className="underline">Ubicación</span>
          </a>
          {sourceUrl && (
            <a
              href={sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              onClick={e => e.stopPropagation()}
              className="text-[9px] font-mono font-bold uppercase tracking-wider opacity-50 hover:opacity-100 transition-opacity flex items-center gap-1"
            >
              {isIg ? '📸 IG' : '🌐 WEB'}
              <span className="underline">Más info</span>
            </a>
          )}
          <Link
            to={`/evento/${evento.slug}`}
            className="text-[9px] font-mono font-bold uppercase tracking-wider opacity-50 hover:opacity-100 transition-opacity ml-auto"
          >
            Ver más →
          </Link>
        </div>
      </div>
    </div>
  )
}
