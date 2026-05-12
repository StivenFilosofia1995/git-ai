import { Link } from 'react-router-dom'
import { useEffect, useRef } from 'react'
import { type Evento, trackInteraccion, getUrgencyLabel } from '../../lib/api'
import { getEventDateParts } from '../../lib/datetime'
import SmartEventImage from '../ui/SmartEventImage'
import { useAuth } from '../../lib/AuthContext'
import { useFavoritos } from '../../lib/useFavoritos'

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
  const { toggle, isSaved } = useFavoritos()
  const cardRef = useRef<HTMLDivElement>(null)
  const viewTracked = useRef(false)
  const saved = isSaved(evento.id)

  const { diaCorto: dia, hora } = getEventDateParts(evento)
  const cat = evento.categoria_principal
  const placeholderColor = CAT_COLORS[cat] ?? '#0a0a0a'
  // Show hora whenever it exists, unless explicitly flagged as unconfirmed (false).
  // null / undefined means "not yet set" — still show the time if the hora field is populated.
  const horaConfirmada = evento.hora_confirmada !== false && hora
  const fechaLabel = horaConfirmada ? `${dia} · ${hora}` : dia
  const horaPrompt = horaConfirmada ? hora : ''

  // ML: urgency score para badge visual
  const urgency = getUrgencyLabel(evento.fecha_inicio)

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
          <div className="flex items-center gap-1.5">
            {urgency === 'alta' && (
              <span className="text-[9px] font-mono font-black uppercase tracking-widest bg-black text-white px-1.5 py-0.5 animate-pulse">
                HOY
              </span>
            )}
            {urgency === 'media' && (
              <span className="text-[9px] font-mono font-bold uppercase tracking-widest border border-black px-1.5 py-0.5 opacity-80">
                PRONTO
              </span>
            )}
            <span className="text-[10px] font-mono font-bold">{fechaLabel}</span>
          </div>
        </div>

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
          {/* WhatsApp share */}
          <a
            href={`https://wa.me/?text=${encodeURIComponent(`📅 *${evento.titulo}*\n🗓 ${dia}${hora ? ` · ${hora}` : ''}\n📍 ${ubicacionLabel || 'Medellín'}\n\nhttps://culturaetereamed.com/evento/${evento.slug}`)}`}
            target="_blank"
            rel="noopener noreferrer"
            onClick={e => e.stopPropagation()}
            title="Compartir por WhatsApp"
            className="text-[11px] opacity-50 hover:opacity-100 transition-opacity"
          >
            <svg viewBox="0 0 24 24" className="w-3.5 h-3.5 fill-current inline" aria-hidden="true">
              <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
            </svg>
          </a>
          {/* Guardar */}
          <button
            type="button"
            onClick={e => { e.stopPropagation(); toggle({ id: evento.id, titulo: evento.titulo, slug: evento.slug, fecha_inicio: evento.fecha_inicio, categoria_principal: evento.categoria_principal, nombre_lugar: evento.nombre_lugar ?? undefined, barrio: evento.barrio ?? undefined, municipio: evento.municipio ?? undefined, imagen_url: evento.imagen_url ?? undefined, es_gratuito: evento.es_gratuito ?? undefined }) }}
            title={saved ? 'Quitar de guardados' : 'Guardar evento'}
            className={`text-[13px] transition-all hover:scale-110 active:scale-95 ${saved ? 'opacity-100' : 'opacity-40 hover:opacity-100'}`}
          >
            {saved ? '♥' : '♡'}
          </button>
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
