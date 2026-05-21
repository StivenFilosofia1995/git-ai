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

// eslint-disable-next-line @typescript-eslint/no-empty-object-type
interface Props {}

export default function EventoDestacado(_props: Props = {}) {
  const [eventos, setEventos] = useState<Evento[]>([])
  const [current, setCurrent] = useState(0)
  const [animating, setAnimating] = useState(false)
  const [open, setOpen] = useState(false)
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
    /* ── Mobile: barra superior (bajo el header). Desktop: barra inferior ── */
    <div
      className="fixed top-14 left-0 right-0 z-50 select-none md:top-auto md:bottom-0"
      style={{ fontFamily: "'Space Mono', monospace" }}
    >
      {/* ── Panel expandido — solo desktop (sube desde la barra) ── */}
      <div
        className="hidden md:block overflow-hidden transition-all duration-300 ease-in-out bg-white border-t-2 border-x-0"
        style={{
          maxHeight: open ? 320 : 0,
          borderColor: accent,
        }}
      >
        <div className={`flex gap-0 transition-opacity duration-300 ${animating ? 'opacity-0' : 'opacity-100'}`}>
          {/* Imagen */}
          <div className="relative shrink-0 w-32 sm:w-48 bg-neutral-100 overflow-hidden" style={{ minHeight: 160 }}>
            {ev.imagen_url ? (
              <img
                src={ev.imagen_url}
                alt={ev.titulo}
                className="w-full h-full object-cover"
                loading="lazy"
                style={{ minHeight: 160 }}
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center" style={{ minHeight: 160, backgroundColor: accent + '18' }}>
                <span className="text-4xl opacity-20">◆</span>
              </div>
            )}
            <div className="absolute top-0 left-0 px-1.5 py-0.5" style={{ backgroundColor: accent }}>
              <span className="text-white text-[8px] font-mono font-black uppercase tracking-[0.15em]">{catLabel}</span>
            </div>
          </div>

          {/* Info */}
          <div className="flex-1 min-w-0 p-3 sm:p-4 flex flex-col justify-between border-l-2 border-black/10">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[9px] font-mono font-black uppercase tracking-wider px-1.5 py-0.5 border" style={{ color: accent, borderColor: accent }}>
                  {dia}{horaLabel ? ` · ${horaLabel}` : ''}
                </span>
                {ev.es_gratuito && (
                  <span className="text-[9px] font-mono font-black uppercase tracking-wider px-1.5 py-0.5 bg-black text-white">GRATIS</span>
                )}
              </div>
              <Link to={`/agenda/${ev.slug}`} className="block group" onClick={() => setOpen(false)}>
                <h3 className="text-black text-sm sm:text-base font-black uppercase leading-tight line-clamp-2 group-hover:opacity-70 transition-opacity">
                  {ev.titulo}
                </h3>
              </Link>
              {lugar && (
                <p className="text-black/50 text-[10px] font-mono mt-1 truncate uppercase tracking-wide">◉ {lugar}</p>
              )}
              {ev.descripcion && (
                <p className="text-black/60 text-[10px] mt-1.5 line-clamp-2 leading-relaxed hidden sm:block">
                  {ev.descripcion}
                </p>
              )}
            </div>
            <Link
              to={`/agenda/${ev.slug}`}
              className="mt-2 self-start text-[9px] font-mono font-black uppercase tracking-widest text-black border border-black px-3 py-1.5 hover:bg-black hover:text-white transition-colors"
              onClick={() => setOpen(false)}
            >
              VER EVENTO →
            </Link>
          </div>

          {/* Dots nav — solo si hay más de 1 */}
          {eventos.length > 1 && (
            <div className="shrink-0 flex flex-col items-center justify-center gap-2 px-3 border-l-2 border-black/10">
              {eventos.map((_, i) => (
                <button
                  key={i}
                  onClick={() => {
                    if (i === current || animating) return
                    setAnimating(true)
                    setTimeout(() => { setCurrent(i); setAnimating(false) }, 300)
                  }}
                  className="transition-all duration-200 rounded-full"
                  style={{
                    width: i === current ? 8 : 5,
                    height: i === current ? 8 : 5,
                    backgroundColor: i === current ? accent : '#d4d4d4',
                  }}
                  aria-label={`Evento ${i + 1}`}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Barra colapsada — siempre visible ── */}
      <div
        className="flex items-center h-11 sm:h-12 bg-white border-b-2 border-t-0 md:border-b-0 md:border-t-2 px-3 sm:px-5 gap-3"
        style={{ borderTopColor: accent, borderBottomColor: accent }}
      >
        {/* Dot animado */}
        <span
          className="w-2.5 h-2.5 rounded-full animate-pulse shrink-0"
          style={{ backgroundColor: accent }}
        />

        {/* Etiqueta */}
        <span className="hidden sm:block text-[9px] font-mono font-black uppercase tracking-[0.25em] text-black/40 shrink-0">
          EVENTOS DEL MES
        </span>
        <span className="hidden sm:block text-black/20 shrink-0 text-xs">|</span>

        {/* Categoría */}
        <span
          className="text-[9px] font-mono font-black uppercase tracking-wider px-1.5 py-0.5 shrink-0 hidden xs:block"
          style={{ color: accent, border: `1px solid ${accent}` }}
        >
          {catLabel}
        </span>

        {/* Título — truncado, clickeable */}
        <button
          type="button"
          onClick={() => setOpen(o => !o)}
          className={`flex-1 min-w-0 text-left transition-opacity duration-300 ${animating ? 'opacity-0' : 'opacity-100'}`}
        >
          <span className="text-xs sm:text-sm font-black uppercase truncate block text-black hover:opacity-60 transition-opacity">
            {ev.titulo}
          </span>
          {lugar && (
            <span className="text-[9px] font-mono text-black/45 truncate block hidden sm:block">
              {dia}{horaLabel ? ` · ${horaLabel}` : ''} · {lugar}
            </span>
          )}
        </button>

        {/* Gratis */}
        {ev.es_gratuito && (
          <span className="hidden md:block shrink-0 text-[9px] font-mono font-black uppercase px-1.5 py-0.5 bg-black text-white">
            GRATIS
          </span>
        )}

        {/* Flechas prev/next */}
        {eventos.length > 1 && (
          <div className="flex items-center gap-1 shrink-0">
            <button
              onClick={() => advance(-1)}
              className="w-7 h-7 flex items-center justify-center text-xs font-mono border border-black/20 hover:bg-black hover:text-white transition-colors"
              aria-label="Evento anterior"
            >
              ←
            </button>
            <span className="text-[9px] font-mono text-black/40 px-1">{current + 1}/{eventos.length}</span>
            <button
              onClick={() => advance(1)}
              className="w-7 h-7 flex items-center justify-center text-xs font-mono border border-black/20 hover:bg-black hover:text-white transition-colors"
              aria-label="Evento siguiente"
            >
              →
            </button>
          </div>
        )}

        {/* Expand / cerrar — solo desktop */}
        <button
          type="button"
          onClick={() => setOpen(o => !o)}
          className="hidden md:flex shrink-0 w-8 h-8 items-center justify-center border-2 border-black hover:bg-black hover:text-white transition-colors ml-1"
          aria-label={open ? 'Cerrar' : 'Ver detalle'}
        >
          <span className="text-[11px] font-mono font-black">{open ? '▼' : '▲'}</span>
        </button>
      </div>
    </div>
  )
}
