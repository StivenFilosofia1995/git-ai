import { useEffect, useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import { getColectivosActivos, type ColectivoActivo } from '../../lib/api'

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
  rock: '#1a1a1a',
  punk: '#1a1a1a',
  libreria: '#10B981',
  casa_cultura: '#3B82F6',
}

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
  rock: 'ROCK',
  punk: 'PUNK',
}

function ColectivoCard({ c }: { c: ColectivoActivo }) {
  const accent = CAT_ACCENT[c.categoria_principal] ?? '#0a0a0a'
  const catLabel = CAT_LABEL[c.categoria_principal] ?? c.categoria_principal?.toUpperCase() ?? '◆'
  const igHandle = c.instagram_handle?.replace(/^@/, '')
  const igUrl = igHandle ? `https://instagram.com/${igHandle}` : null

  return (
    <div
      className="flex-shrink-0 w-44 border-2 border-black bg-white hover:bg-black hover:text-white transition-colors duration-200 group"
      style={{ borderColor: accent }}
    >
      {/* Color bar top */}
      <div className="h-1 w-full" style={{ backgroundColor: accent }} />

      <div className="p-3">
        {/* Category */}
        <span
          className="text-[8px] font-mono font-black uppercase tracking-[0.2em]"
          style={{ color: accent }}
        >
          {catLabel}
        </span>

        {/* Name */}
        <Link
          to={`/espacios/${c.slug}`}
          className="block mt-1 text-[11px] font-black uppercase leading-tight line-clamp-2 group-hover:text-white"
          style={{ fontFamily: "'Sora', 'Arial Black', sans-serif" }}
        >
          {c.nombre}
        </Link>

        {/* Instagram handle */}
        {igUrl && igHandle && (
          <a
            href={igUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="block mt-2 text-[10px] font-mono text-neutral-500 group-hover:text-neutral-300 hover:underline truncate"
            onClick={e => e.stopPropagation()}
          >
            @{igHandle}
          </a>
        )}

        {/* Event count badge */}
        <div className="flex items-center justify-between mt-2 pt-1.5 border-t border-black/10 group-hover:border-white/20">
          <span className="text-[9px] font-mono font-bold uppercase">
            {c.barrio || c.municipio || ''}
          </span>
          <span
            className="text-[9px] font-mono font-black px-1.5 py-0.5"
            style={{ backgroundColor: accent, color: '#fff' }}
          >
            {c.proximos_eventos} eventos
          </span>
        </div>
      </div>
    </div>
  )
}

interface Props {
  className?: string
}

export default function ColectivosStrip({ className = '' }: Props) {
  const [colectivos, setColectivos] = useState<ColectivoActivo[]>([])
  const stripRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    getColectivosActivos(24)
      .then(setColectivos)
      .catch(() => setColectivos([]))
  }, [])

  if (colectivos.length === 0) return null

  return (
    <section className={`border-b-2 border-black ${className}`}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-5">
        {/* Header */}
        <div className="flex items-center gap-3 mb-4">
          <span className="w-3 h-3 bg-black" />
          <span className="text-[11px] font-mono font-black uppercase tracking-[0.3em]">
            Colectivos activos esta semana
          </span>
          <span className="text-[9px] font-mono text-neutral-400 uppercase tracking-wider">
            {colectivos.length} con eventos
          </span>
          <Link
            to="/espacios"
            className="ml-auto text-[9px] font-mono font-bold uppercase tracking-widest underline hover:no-underline"
          >
            Ver todos →
          </Link>
        </div>

        {/* Scrollable strip */}
        <div
          ref={stripRef}
          className="flex gap-3 overflow-x-auto pb-2 -mx-4 px-4 sm:mx-0 sm:px-0"
          style={{ scrollbarWidth: 'thin' }}
        >
          {colectivos.map(c => (
            <ColectivoCard key={c.id} c={c} />
          ))}
        </div>

        {/* Pequeña nota */}
        <p className="text-[9px] font-mono text-neutral-400 mt-3">
          Cada colectivo tiene su Instagram vinculado — hacé clic para seguirlos directamente.
        </p>
      </div>
    </section>
  )
}
