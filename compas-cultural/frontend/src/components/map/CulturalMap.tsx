import { useEffect, useMemo, useState } from 'react'
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet'
import MarkerClusterGroup from '@changey/react-leaflet-markercluster'
import 'leaflet/dist/leaflet.css'
import '@changey/react-leaflet-markercluster/dist/styles.min.css'
import { getEspacios, getEventosTodos, type Espacio, type Evento, type Zona } from '../../lib/api'

// ── Zona matching helpers (mirrors Agenda.tsx logic) ─────────────────────────
function normalizeZonaText(value: string | null | undefined): string {
  if (!value) return ''
  return value
    .normalize('NFD')
    .replaceAll(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replaceAll(/[_\-\u2013\u2014]+/g, ' ')
    .replaceAll(/\s+/g, ' ')
    .trim()
}

function buildZonaTokens(zonaNombre: string): string[] {
  const normalized = (zonaNombre || '')
    .normalize('NFD')
    .replaceAll(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replaceAll(/[_\-\u2013\u2014]+/g, ' - ')
    .replaceAll(/\s+/g, ' ')
    .trim()
  if (!normalized) return []
  const noParen = normalized.replaceAll(/\(.*?\)/g, '').trim()
  const noDash = noParen.replaceAll(/\s+-\s+/g, ' ').trim()
  const parts = noParen.split(/\s+-\s+/).map((t: string) => t.trim()).filter(Boolean)
  const candidates = [normalized, noParen, noDash, ...parts]
    .map((t: string) => normalizeZonaText(t.replace(/^(barrio|comuna|sector|zona)\s+/i, '')))
    .filter(Boolean)
  return Array.from(new Set(candidates))
}

function itemMatchesZona(item: { barrio?: string | null; municipio?: string | null; nombre?: string; titulo?: string; nombre_lugar?: string | null; descripcion?: string | null }, zona: Zona): boolean {
  const tokens = buildZonaTokens(zona.nombre)
  if (!tokens.length) return true
  const municipioZona = normalizeZonaText(zona.municipio)
  const municipioItem = normalizeZonaText(item.municipio)
  if (municipioZona && municipioItem && !municipioItem.includes(municipioZona)) return false
  const fields = [
    normalizeZonaText(item.barrio),
    normalizeZonaText(item.nombre_lugar),
    normalizeZonaText((item as { nombre?: string }).nombre),
    normalizeZonaText(item.titulo),
    normalizeZonaText(item.descripcion),
  ].filter(Boolean)
  return tokens.some(token => fields.some(field => field.includes(token)))
}

const CAT_MARKER_COLORS: Record<string, string> = {
  teatro: '#DC2626',
  hip_hop: '#F59E0B',
  jazz: '#7C3AED',
  galeria: '#EC4899',
  libreria: '#10B981',
  casa_cultura: '#3B82F6',
  electronica: '#06B6D4',
  danza: '#F97316',
  arte_contemporaneo: '#EC4899',
  muralismo: '#F59E0B',
  fotografia: '#7C3AED',
  musica_en_vivo: '#06B6D4',
  batalla_freestyle: '#F59E0B',
  espacio_hibrido: '#6B7280',
  poesia: '#8B5CF6',
  festival: '#F97316',
  centro_cultural: '#3B82F6',
  cine: '#DC2626',
  circo: '#F97316',
  editorial: '#10B981',
  radio_comunitaria: '#06B6D4',
  filosofia: '#8B5CF6',
}

const ALL_CATS = [
  'teatro', 'hip_hop', 'jazz', 'galeria', 'libreria', 'casa_cultura', 'electronica', 'danza',
  'arte_contemporaneo', 'centro_cultural', 'musica_en_vivo', 'muralismo', 'fotografia',
  'batalla_freestyle', 'poesia', 'festival', 'espacio_hibrido', 'cine',
]

const catLabels: Record<string, string> = {
  teatro: 'Teatro', hip_hop: 'Hip Hop', jazz: 'Jazz', galeria: 'Galerías',
  libreria: 'Librerías', casa_cultura: 'Casas Cultura', electronica: 'Electrónica',
  danza: 'Danza', arte_contemporaneo: 'Arte Contemp.', centro_cultural: 'Centros Cult.',
  musica_en_vivo: 'Música en Vivo', muralismo: 'Muralismo', fotografia: 'Fotografía',
  batalla_freestyle: 'Freestyle', poesia: 'Poesía', festival: 'Festivales',
  espacio_hibrido: 'Híbrido', cine: 'Cine',
}

function FitBounds({ coords }: { coords: [number, number][] }) {
  const map = useMap()
  useEffect(() => {
    if (coords.length === 0) return
    if (coords.length === 1) {
      map.setView(coords[0], 14)
    } else {
      const bounds = coords.reduce(
        (b, c) => b.extend(c),
        map.getBounds().pad(-1),
      )
      try { map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 }) } catch { /* ignore */ }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [coords.length])
  return null
}

interface CulturalMapProps {
  /** Slug of the zona to highlight/filter (from Agenda page) */
  zonaFilter?: string
  /** Full zona list to resolve slug → zona object */
  zonas?: Zona[]
}

export default function CulturalMap({ zonaFilter, zonas = [] }: CulturalMapProps = {}) {
  const [espacios, setEspacios] = useState<Espacio[]>([])
  const [eventos, setEventos] = useState<Evento[]>([])
  const [activeCats, setActiveCats] = useState<Set<string>>(new Set(ALL_CATS))
  const [showAllCats, setShowAllCats] = useState(false)
  const [showEquipamientos, setShowEquipamientos] = useState(true)
  const [showEventos, setShowEventos] = useState(true)
  // Mobile: panel hidden by default; desktop always shown via CSS
  const [filtersOpen, setFiltersOpen] = useState(false)

  // Resolve zona object from slug
  const zonaActiva = useMemo(
    () => (zonaFilter ? zonas.find(z => z.slug === zonaFilter) ?? null : null),
    [zonaFilter, zonas],
  )

  useEffect(() => {
    getEspacios({ limit: 1000 }).then(setEspacios).catch(console.error)
    getEventosTodos({ maxRows: 500 })
      .then(evs => {
        const hoy = new Date().toISOString().slice(0, 10)
        const cutoff = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10)
        setEventos(evs.filter(e => e.lat != null && e.lng != null && e.fecha_inicio >= hoy && e.fecha_inicio <= cutoff))
      })
      .catch(() => {})
  }, [])

  const filtered = useMemo(() =>
    espacios.filter(e => {
      const lat = e.lat ?? e.coordenadas?.lat
      const lng = e.lng ?? e.coordenadas?.lng
      if (!lat || !lng) return false
      if (e.es_equipamiento_publico && !showEquipamientos) return false
      if (!(activeCats.has(e.categoria_principal) || !ALL_CATS.includes(e.categoria_principal))) return false
      if (zonaActiva && !itemMatchesZona(e, zonaActiva)) return false
      return true
    }),
  [espacios, activeCats, showEquipamientos, zonaActiva])

  const filteredEventos = useMemo(() =>
    eventos.filter(ev => !zonaActiva || itemMatchesZona(ev, zonaActiva)),
  [eventos, zonaActiva])

  const coords = useMemo<[number, number][]>(() => {
    const espacioCoords = filtered.map(e => [e.lat ?? e.coordenadas?.lat ?? 0, e.lng ?? e.coordenadas?.lng ?? 0] as [number, number])
    if (zonaActiva && filteredEventos.length > 0) {
      const evCoords = filteredEventos
        .filter(ev => ev.lat && ev.lng)
        .map(ev => [ev.lat!, ev.lng!] as [number, number])
      return [...espacioCoords, ...evCoords]
    }
    return espacioCoords
  }, [filtered, filteredEventos, zonaActiva])

  const toggleCat = (cat: string) => {
    setActiveCats(prev => {
      const next = new Set(prev)
      if (next.has(cat)) next.delete(cat); else next.add(cat)
      return next
    })
  }

  const mainCats = ALL_CATS.slice(0, 8)
  const extraCats = ALL_CATS.slice(8)
  const espaciosConCoords = espacios.filter(e => (e.lat ?? e.coordenadas?.lat) && (e.lng ?? e.coordenadas?.lng)).length

  const filterPanel = (
    <div className="p-4 h-full overflow-y-auto">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-mono font-black text-xs uppercase tracking-[0.2em]">Filtros</h3>
        {/* Close button — only visible inside panel on mobile */}
        <button
          type="button"
          onClick={() => setFiltersOpen(false)}
          className="sm:hidden text-[11px] font-mono font-bold px-2 py-1 border border-black/20 hover:bg-black hover:text-white transition-colors"
        >
          ✕
        </button>
      </div>

      <div className="space-y-1.5">
        {mainCats.map(cat => (
          <label key={cat} className="flex items-center gap-2 text-xs cursor-pointer py-0.5">
            <input type="checkbox" className="rounded" checked={activeCats.has(cat)} onChange={() => toggleCat(cat)} />
            <span className="w-2 h-2 rounded-full inline-block shrink-0" style={{ backgroundColor: CAT_MARKER_COLORS[cat] }} />
            <span className="truncate">{catLabels[cat] ?? cat}</span>
          </label>
        ))}
        {showAllCats && extraCats.map(cat => (
          <label key={cat} className="flex items-center gap-2 text-xs cursor-pointer py-0.5">
            <input type="checkbox" className="rounded" checked={activeCats.has(cat)} onChange={() => toggleCat(cat)} />
            <span className="w-2 h-2 rounded-full inline-block shrink-0" style={{ backgroundColor: CAT_MARKER_COLORS[cat] ?? '#6B7280' }} />
            <span className="truncate">{catLabels[cat] ?? cat}</span>
          </label>
        ))}
        {extraCats.length > 0 && (
          <button type="button" onClick={() => setShowAllCats(v => !v)}
            className="text-[10px] font-mono font-bold uppercase tracking-wider hover:underline mt-1">
            {showAllCats ? '▲ Menos' : `▼ +${extraCats.length} más`}
          </button>
        )}
      </div>

      <div className="border-t-2 border-black mt-3 pt-3 space-y-2">
        <label className="flex items-center gap-2 text-xs cursor-pointer">
          <input type="checkbox" className="rounded" checked={showEquipamientos} onChange={() => setShowEquipamientos(v => !v)} />
          <span className="font-bold">★ Equipamientos Públicos</span>
        </label>
        <p className="text-[9px] font-mono opacity-50 -mt-1">UVAs · Bibliotecas · Teatros oficiales</p>

        <label className="flex items-center gap-2 text-xs cursor-pointer">
          <input type="checkbox" className="rounded" checked={showEventos} onChange={() => setShowEventos(v => !v)} />
          <span className="inline-flex items-center gap-1.5 font-bold">
            <span className="w-2.5 h-2.5 rounded-full bg-red-500 inline-block" />
            Eventos próximos
          </span>
        </label>
        <p className="text-[9px] font-mono opacity-50 -mt-1">
          {showEventos && eventos.length > 0 ? `${eventos.length} eventos en el mapa` : 'Hoy y próximos 7 días'}
        </p>
      </div>
        {zonaActiva && (
          <div className="mt-3 pt-2 border-t border-black/10">
            <span className="text-[10px] font-mono font-black uppercase tracking-wider text-black">
              Zona: {zonaActiva.nombre}
            </span>
            <p className="text-[9px] font-mono opacity-50 mt-0.5">Mostrando solo esta zona</p>
          </div>
        )}      <p className="text-[10px] font-mono font-black mt-3 pt-2 border-t border-black/10 uppercase tracking-wider">
        {filtered.length} / {espaciosConCoords} lugares
      </p>
    </div>
  )

  return (
    <div className="relative">
      {/* MAP — responsive height */}
      <MapContainer
        center={[6.2442, -75.5812]}
        zoom={12}
        minZoom={10}
        maxZoom={18}
        scrollWheelZoom
        className="w-full h-[55vh] min-h-[320px] sm:h-[620px] z-0"
        style={{ background: '#f8f8f8' }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> · <a href="https://carto.com/">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
        />
        <FitBounds coords={coords} />

        <MarkerClusterGroup chunkedLoading>
          {filtered.map(espacio => {
            const lat = espacio.lat ?? espacio.coordenadas?.lat ?? 0
            const lng = espacio.lng ?? espacio.coordenadas?.lng ?? 0
            const color = CAT_MARKER_COLORS[espacio.categoria_principal] ?? '#6B7280'
            const isPublico = !!espacio.es_equipamiento_publico
            return (
              <CircleMarker
                key={espacio.id}
                center={[lat, lng]}
                radius={isPublico ? 10 : 7}
                pathOptions={{
                  fillColor: color, fillOpacity: isPublico ? 0.95 : 0.85,
                  color: isPublico ? '#000' : '#fff', weight: isPublico ? 2.5 : 2,
                  dashArray: isPublico ? '4 2' : undefined,
                }}
              >
                <Popup>
                  <a href={`/espacio/${espacio.slug}`}
                    style={{ textDecoration: 'none', color: 'inherit', display: 'block', fontFamily: "'Space Mono', monospace" }}>
                    <div style={{ fontWeight: 700, fontSize: 12, marginBottom: 2 }}>
                      {isPublico && <span title="Equipamiento público">★ </span>}{espacio.nombre}
                    </div>
                    <div style={{ fontSize: 10, color: '#666', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                      {espacio.categoria_principal.replace(/_/g, ' ')}
                    </div>
                    {espacio.barrio && (
                      <div style={{ fontSize: 10, color: '#999', marginTop: 2 }}>◉ {espacio.barrio}, {espacio.municipio}</div>
                    )}
                    <div style={{ fontSize: 9, color: '#000', marginTop: 4, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px' }}>Ver detalle →</div>
                  </a>
                </Popup>
              </CircleMarker>
            )
          })}
        </MarkerClusterGroup>

        {showEventos && (
          <MarkerClusterGroup chunkedLoading>
            {filteredEventos.map(ev => {
              const lat = ev.lat ?? 0
              const lng = ev.lng ?? 0
              const fecha = ev.fecha_inicio?.slice(0, 10) ?? ''
              const esHoy = fecha === new Date().toISOString().slice(0, 10)
              return (
                <CircleMarker
                  key={ev.id}
                  center={[lat, lng]}
                  radius={esHoy ? 9 : 6}
                  pathOptions={{ fillColor: esHoy ? '#EF4444' : '#F97316', fillOpacity: 0.9, color: '#fff', weight: esHoy ? 2 : 1.5 }}
                >
                  <Popup>
                    <a href={`/evento/${ev.slug}`}
                      style={{ textDecoration: 'none', color: 'inherit', display: 'block', fontFamily: "'Space Mono', monospace", maxWidth: 200 }}>
                      {esHoy && <div style={{ fontSize: 9, fontWeight: 700, color: '#EF4444', textTransform: 'uppercase', marginBottom: 2 }}>● HOY</div>}
                      <div style={{ fontWeight: 700, fontSize: 12, marginBottom: 2, lineHeight: 1.3 }}>{ev.titulo}</div>
                      <div style={{ fontSize: 10, color: '#666' }}>{fecha}</div>
                      {ev.nombre_lugar && <div style={{ fontSize: 10, color: '#999', marginTop: 2 }}>◉ {ev.nombre_lugar}</div>}
                      {ev.es_gratuito && <div style={{ fontSize: 9, fontWeight: 700, color: '#10B981', marginTop: 2 }}>GRATIS</div>}
                      <div style={{ fontSize: 9, color: '#000', marginTop: 4, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px' }}>Ver evento →</div>
                    </a>
                  </Popup>
                </CircleMarker>
              )
            })}
          </MarkerClusterGroup>
        )}
      </MapContainer>

      {/* ── DESKTOP: always-visible left floating panel ─────────────────── */}
      <div className="hidden sm:block absolute top-4 left-4 w-52 max-h-[75vh] bg-white/95 backdrop-blur-sm border-2 border-black z-[1000] shadow-sm">
        {filterPanel}
      </div>

      {/* ── MOBILE: toggle button bottom-left ──────────────────────────── */}
      <button
        type="button"
        onClick={() => setFiltersOpen(v => !v)}
        className="sm:hidden absolute bottom-4 left-4 z-[1001] flex items-center gap-2 bg-black text-white font-mono text-[11px] font-bold uppercase tracking-widest px-3 py-2.5 shadow-lg active:scale-95 transition-transform"
      >
        <span>{filtersOpen ? '✕' : '⊞'}</span>
        <span>{filtersOpen ? 'Cerrar' : 'Filtros'}</span>
        {!filtersOpen && (
          <span className="bg-yellow-300 text-black px-1.5 py-0.5 text-[9px] font-black rounded-sm">
            {filtered.length}
          </span>
        )}
      </button>

      {/* ── MOBILE: bottom sheet panel ─────────────────────────────────── */}
      {filtersOpen && (
        <div className="sm:hidden absolute bottom-0 left-0 right-0 z-[1000] bg-white border-t-2 border-black max-h-[55vh] overflow-y-auto shadow-2xl">
          {filterPanel}
        </div>
      )}
    </div>
  )
}
