import { Link } from 'react-router-dom'
import { useEffect, useRef } from 'react'
import { type Evento, trackInteraccion } from '../../lib/api'
import { formatEventTime, hasReliableEventTime, relativeDayLabel } from '../../lib/datetime'
import SmartEventImage from '../ui/SmartEventImage'
import { useAuth } from '../../lib/AuthContext'
import { useFavoritos } from '../../lib/useFavoritos'

interface EventCardProps {
  evento: Evento
  compact?: boolean
}

export const CAT_COLORS: Record<string, string> = {
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

const CAT_LABELS: Record<string, string> = {
  hip_hop: 'Hip hop',
  arte_contemporaneo: 'Arte contemporáneo',
  galeria: 'Galería',
  libreria: 'Librería',
  casa_cultura: 'Casa de cultura',
  electronica: 'Electrónica',
  musica_en_vivo: 'Música en vivo',
  batalla_freestyle: 'Freestyle',
  poesia: 'Poesía',
  fotografia: 'Fotografía',
  filosofia: 'Filosofía',
}

export function categoriaLabel(cat?: string | null): string {
  if (!cat) return 'Cultura'
  return CAT_LABELS[cat] ?? cat.replaceAll('_', ' ').replace(/^\w/, c => c.toUpperCase())
}

function capitalizar(texto?: string | null): string {
  if (!texto) return ''
  // Por palabra: \b\w falla con tildes ("Belén" → "BeléN")
  return texto.replaceAll('_', ' ').split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
}

/**
 * Tarjeta mínima pensada para el usuario perezoso:
 * cuándo (día + hora) → qué → dónde → precio → 1 acción.
 */
export default function EventCard({ evento, compact }: Readonly<EventCardProps>) {
  const { user } = useAuth()
  const { isSaved, toggle } = useFavoritos()
  const cardRef = useRef<HTMLElement>(null)
  const viewTracked = useRef(false)

  const cat = evento.categoria_principal
  const placeholderColor = CAT_COLORS[cat] ?? '#0a0a0a'
  const dia = relativeDayLabel(evento.fecha_inicio)
  const hora = hasReliableEventTime(evento) ? formatEventTime(evento) : null
  const esHoy = dia === 'Hoy'

  const lugar = evento.nombre_lugar || capitalizar(evento.barrio) || capitalizar(evento.municipio) || 'Valle de Aburrá'
  const zona = [evento.barrio, evento.municipio].map(capitalizar).filter(Boolean).find(z => z !== lugar)
  const mapsTarget = [evento.nombre_lugar, evento.direccion, evento.barrio, evento.municipio].filter(Boolean).join(', ')
  const mapsUrl = evento.lat && evento.lng
    ? `https://www.google.com/maps/dir/?api=1&destination=${evento.lat},${evento.lng}`
    : `https://www.google.com/maps/search/${encodeURIComponent(mapsTarget || `${evento.titulo}, Medellín`)}`
  const guardado = isSaved(evento.id)

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
      { threshold: 0.5 },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [user, evento.id, cat, evento.barrio, evento.municipio])

  const handleClick = () => {
    if (user) {
      void trackInteraccion('click', evento.id, cat, user.id, {
        barrio: evento.barrio ?? undefined,
        municipio: evento.municipio ?? undefined,
      })
    }
  }

  const compartir = async () => {
    const url = `${window.location.origin}/evento/${evento.slug}`
    const texto = `${evento.titulo} · ${dia}${hora ? ` ${hora}` : ''} · ${lugar}`
    try {
      if (navigator.share) {
        await navigator.share({ title: evento.titulo, text: texto, url })
        return
      }
      await navigator.clipboard.writeText(`${texto}\n${url}`)
    } catch { /* el usuario canceló */ }
  }

  const placeholder = (
    <div
      className="w-full h-full flex items-center justify-center"
      style={{ backgroundColor: placeholderColor }}
    >
      <span className="text-white/90 text-xs font-mono font-bold uppercase tracking-widest">
        ◈ {categoriaLabel(cat)}
      </span>
    </div>
  )

  return (
    <article
      ref={cardRef}
      className="group bg-white border-2 border-black flex flex-col overflow-hidden transition-shadow hover:shadow-[6px_6px_0_0_#000]"
    >
      <Link
        to={`/evento/${evento.slug}`}
        onClick={handleClick}
        className={`relative block ${compact ? 'aspect-[2/1]' : 'aspect-[16/9]'} overflow-hidden border-b-2 border-black`}
      >
        {evento.imagen_url ? (
          <SmartEventImage
            primaryUrl={evento.imagen_url}
            sourceUrl={evento.fuente_url}
            alt={evento.titulo}
            kind="card"
            className="w-full h-full object-cover motion-safe:group-hover:scale-105 transition-transform duration-500"
            fallback={placeholder}
          />
        ) : placeholder}
        {evento.es_gratuito && (
          <span className="absolute top-2 left-2 bg-[#FACC15] text-black text-xs font-black uppercase tracking-wide px-2 py-1 border-2 border-black">
            Gratis
          </span>
        )}
        {typeof evento.distancia_km === 'number' && (
          <span className="absolute top-2 right-2 bg-black text-white text-xs font-bold px-2 py-1">
            {evento.distancia_km < 1 ? `${Math.round(evento.distancia_km * 1000)} m` : `${evento.distancia_km.toFixed(1)} km`}
          </span>
        )}
      </Link>

      <div className="p-4 flex flex-col flex-1 gap-1.5">
        <p className="text-sm font-bold">
          <span className={esHoy ? 'bg-black text-white px-1.5 py-0.5 mr-1' : 'mr-1'}>{dia}</span>
          {hora && <span>{hora}</span>}
          {!hora && <span className="text-black/50 font-normal text-xs">hora por confirmar</span>}
        </p>

        <Link to={`/evento/${evento.slug}`} onClick={handleClick}>
          <h3 className="font-heading font-black text-base leading-snug line-clamp-2 group-hover:underline">
            {evento.titulo}
          </h3>
        </Link>

        <p className="text-sm text-black/70 truncate">
          {lugar}{zona ? <span className="text-black/50"> · {zona}</span> : null}
        </p>

        <p className="text-xs text-black/60">
          {categoriaLabel(cat)}
          {!evento.es_gratuito && evento.precio ? ` · ${evento.precio}` : ''}
        </p>

        <div className="mt-auto pt-3 flex items-center gap-1.5">
          <a
            href={mapsUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-1 min-w-0 text-center text-sm font-bold whitespace-nowrap border-2 border-black px-2 py-2.5 hover:bg-black hover:text-white transition-colors"
          >
            Cómo llegar
          </a>
          {evento.fuente_url && (
            <a
              href={evento.fuente_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 min-w-0 text-center text-sm font-bold whitespace-nowrap bg-black text-white border-2 border-black px-2 py-2.5 hover:bg-white hover:text-black transition-colors"
            >
              {evento.precio && !evento.es_gratuito ? 'Entradas' : 'Más info'}
            </a>
          )}
          <button
            type="button"
            onClick={() => toggle({
              id: evento.id,
              titulo: evento.titulo,
              slug: evento.slug,
              fecha_inicio: evento.fecha_inicio,
              categoria_principal: evento.categoria_principal,
              nombre_lugar: evento.nombre_lugar ?? undefined,
              barrio: evento.barrio ?? undefined,
              municipio: evento.municipio ?? undefined,
              imagen_url: evento.imagen_url ?? undefined,
              es_gratuito: evento.es_gratuito,
            })}
            aria-label={guardado ? 'Quitar de guardados' : 'Guardar evento'}
            aria-pressed={guardado}
            className="w-11 h-11 shrink-0 border-2 border-black text-lg flex items-center justify-center hover:bg-black hover:text-white transition-colors"
          >
            {guardado ? '♥' : '♡'}
          </button>
          <button
            type="button"
            onClick={compartir}
            aria-label="Compartir evento"
            className="w-11 h-11 shrink-0 border-2 border-black text-lg flex items-center justify-center hover:bg-black hover:text-white transition-colors"
          >
            ↗
          </button>
        </div>
      </div>
    </article>
  )
}
