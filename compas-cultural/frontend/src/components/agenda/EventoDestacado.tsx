import { useEffect, useState, useRef, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { getEventosDestacados, type Evento } from '../../lib/api'
import { getEventDateParts } from '../../lib/datetime'

const CAT_LABEL: Record<string, string> = {
  teatro: 'TEATRO',
  hip_hop: 'HIP HOP',
  jazz: 'JAZZ',
  galeria: 'GALERÍA',
  arte_contemporaneo: 'ARTE',
  libreria: 'LIBRERÍA',
  casa_cultura: 'CULTURA',
  electronica: 'ELECTRÓNICA',
  danza: 'DANZA',
  musica_en_vivo: 'MÚSICA',
  batalla_freestyle: 'FREESTYLE',
  poesia: 'POESÍA',
  festival: 'FESTIVAL',
  cine: 'CINE',
  fotografia: 'FOTO',
  muralismo: 'MURAL',
  filosofia: 'FILOSOFÍA',
  taller: 'TALLER',
  circo: 'CIRCO',
  radio_comunitaria: 'RADIO',
}

const CAT_ACCENT: Record<string, string> = {
  teatro: '#DC2626',
  hip_hop: '#F59E0B',
  jazz: '#7C3AED',
  galeria: '#EC4899',
  arte_contemporaneo: '#EC4899',
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
}

interface Props {
  className?: string
}

export default function EventoDestacado({ className = '' }: Props) {
  const [eventos, setEventos] = useState<Evento[]>([])
  const [current, setCurrent] = useState(0)
  const [animating, setAnimating] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    const fetch = () => {
      getEventosDestacados(5)
        .then(data => {
          setEventos(data)
          setCurrent(0)
        })
        .catch(() => setEventos([]))
    }
    fetch()
    // Re-fetch cada hora → eventos expirados desaparecen automáticamente
    const id = setInterval(fetch, 60 * 60 * 1000)
    return () => clearInterval(id)
  }, [])

  const advance = useCallback((dir: 1 | -1) => {
    if (animating || eventos.length === 0) return
    setAnimating(true)
    setTimeout(() => {
      setCurrent(c => (c + dir + eventos.length) % eventos.length)
      setAnimating(false)
    }, 300)
  }, [animating, eventos.length])

  useEffect(() => {
    if (eventos.length <= 1) return
    intervalRef.current = setInterval(() => advance(1), 6000)
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [eventos.length, advance])

  if (eventos.length === 0) return null

  const ev = eventos[current]
  const { diaCorto: dia, hora } = getEventDateParts(ev)
  const horaLabel = ev.hora_confirmada ? hora : null
  const catLabel = CAT_LABEL[ev.categoria_principal] ?? ev.categoria_principal?.toUpperCase() ?? 'EVENTO'
  const accent = CAT_ACCENT[ev.categoria_principal] ?? '#0a0a0a'
  const lugar = [ev.nombre_lugar, ev.barrio].filter(Boolean).join(' · ')

  return (
    <div className={`select-none ${className}`}>
      {/* Header — broadcast ticker */}
      <div className="flex items-center gap-2 mb-2">
        <div
          className="w-2 h-2 rounded-full animate-pulse"
          style={{ backgroundColor: accent }}
        />
        <span className="text-[9px] font-mono font-black uppercase tracking-[0.3em] text-neutral-400">
          EVENTOS DEL MES
        </span>
        {eventos.length > 1 && (
          <span className="ml-auto text-[9px] font-mono text-neutral-600">
            {current + 1}/{eventos.length}
          </span>
        )}
      </div>

      {/* Card */}
      <div
        className="border-2 border-black bg-black overflow-hidden"
        style={{ borderColor: accent }}
      >
        {/* Image area */}
        <div className="relative w-full aspect-[4/3] overflow-hidden bg-neutral-900">
          {ev.imagen_url ? (
            <img
              src={ev.imagen_url}
              alt={ev.titulo}
              className={`w-full h-full object-cover transition-opacity duration-300 ${animating ? 'opacity-0' : 'opacity-100'}`}
              loading="lazy"
            />
          ) : (
            <div
              className="w-full h-full flex items-center justify-center"
              style={{ backgroundColor: accent + '22' }}
            >
              <span className="text-5xl opacity-30">◆</span>
            </div>
          )}

          {/* Category badge — top-left football-style overlay */}
          <div
            className="absolute top-0 left-0 px-2 py-1"
            style={{ backgroundColor: accent }}
          >
            <span className="text-white text-[9px] font-mono font-black uppercase tracking-[0.2em]">
              {catLabel}
            </span>
          </div>

          {/* Date badge — top-right */}
          <div className="absolute top-0 right-0 bg-black px-2 py-1">
            <span className="text-white text-[9px] font-mono font-bold uppercase">
              {dia}
              {horaLabel && (
                <span className="text-neutral-400"> · {horaLabel}</span>
              )}
            </span>
          </div>

          {/* LIVE ticker line at bottom of image */}
          <div
            className="absolute bottom-0 left-0 right-0 h-0.5"
            style={{ backgroundColor: accent }}
          />
        </div>

        {/* Info strip */}
        <div
          className={`p-3 transition-opacity duration-300 ${animating ? 'opacity-0' : 'opacity-100'}`}
        >
          <Link
            to={`/agenda/${ev.slug}`}
            className="block group"
          >
            <h3 className="text-white text-sm font-black uppercase leading-tight line-clamp-2 group-hover:text-neutral-300 transition-colors">
              {ev.titulo}
            </h3>
          </Link>

          {lugar && (
            <p className="text-neutral-500 text-[10px] font-mono mt-1 truncate uppercase tracking-wide">
              {lugar}
            </p>
          )}

          {ev.descripcion && (
            <p className="text-neutral-400 text-[10px] mt-1.5 line-clamp-2 leading-relaxed">
              {ev.descripcion}
            </p>
          )}

          <div className="flex items-center justify-between mt-2">
            {ev.es_gratuito && (
              <span
                className="text-[9px] font-mono font-black uppercase tracking-wide px-1.5 py-0.5 border"
                style={{ color: accent, borderColor: accent }}
              >
                GRATIS
              </span>
            )}
            <Link
              to={`/agenda/${ev.slug}`}
              className="ml-auto text-[9px] font-mono font-bold uppercase tracking-widest text-white hover:text-neutral-300 transition-colors flex items-center gap-1"
            >
              VER →
            </Link>
          </div>
        </div>
      </div>

      {/* Navigation dots */}
      {eventos.length > 1 && (
        <div className="flex items-center justify-center gap-1.5 mt-2">
          {eventos.map((_, i) => (
            <button
              key={i}
              onClick={() => {
                if (i === current || animating) return
                setAnimating(true)
                setTimeout(() => { setCurrent(i); setAnimating(false) }, 300)
              }}
              className="transition-all duration-200"
              style={{
                width: i === current ? 16 : 4,
                height: 4,
                borderRadius: 2,
                backgroundColor: i === current ? accent : '#404040',
              }}
              aria-label={`Ir a evento ${i + 1}`}
            />
          ))}
        </div>
      )}

      {/* Prev/Next arrows */}
      {eventos.length > 1 && (
        <div className="flex gap-1 mt-1.5">
          <button
            onClick={() => advance(-1)}
            className="flex-1 py-1 text-neutral-600 hover:text-white text-xs font-mono transition-colors border border-neutral-800 hover:border-neutral-600"
          >
            ←
          </button>
          <button
            onClick={() => advance(1)}
            className="flex-1 py-1 text-neutral-600 hover:text-white text-xs font-mono transition-colors border border-neutral-800 hover:border-neutral-600"
          >
            →
          </button>
        </div>
      )}
    </div>
  )
}
