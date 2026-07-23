import { useEffect, useMemo, useState } from 'react'
import { MapContainer, TileLayer, CircleMarker, Popup, useMap, GeoJSON } from 'react-leaflet'
import MarkerClusterGroup from '@changey/react-leaflet-markercluster'
import 'leaflet/dist/leaflet.css'
import '@changey/react-leaflet-markercluster/dist/styles.min.css'
import { getEspacios, getEventosTodos, type Espacio, type Evento, type Zona } from '../../lib/api'

// ── Geo helpers ───────────────────────────────────────────────────────────────
function normalizeZonaText(value: string | null | undefined): string {
  if (!value) return ''
  return value.normalize('NFD').replaceAll(/[̀-ͯ]/g, '').toLowerCase()
    .replaceAll(/[_\-–—]+/g, ' ').replaceAll(/\s+/g, ' ').trim()
}

function normalizeKey(str: string | null | undefined): string {
  if (!str) return ''
  return str.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[\s-]+/g, '_').trim()
}

function buildZonaTokens(zonaNombre: string): string[] {
  const normalized = (zonaNombre || '').normalize('NFD').replaceAll(/[̀-ͯ]/g, '')
    .toLowerCase().replaceAll(/[_\-–—]+/g, ' - ').replaceAll(/\s+/g, ' ').trim()
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
    normalizeZonaText(item.barrio), normalizeZonaText(item.nombre_lugar),
    normalizeZonaText((item as { nombre?: string }).nombre),
    normalizeZonaText(item.titulo), normalizeZonaText(item.descripcion),
  ].filter(Boolean)
  return tokens.some(token => fields.some(field => field.includes(token)))
}

// ── Constants ─────────────────────────────────────────────────────────────────
const CAT_MARKER_COLORS: Record<string, string> = {
  teatro: '#DC2626', hip_hop: '#F59E0B', jazz: '#7C3AED', galeria: '#EC4899',
  libreria: '#10B981', casa_cultura: '#3B82F6', electronica: '#06B6D4',
  danza: '#F97316', arte_contemporaneo: '#EC4899', muralismo: '#F59E0B',
  fotografia: '#7C3AED', musica_en_vivo: '#06B6D4', batalla_freestyle: '#F59E0B',
  espacio_hibrido: '#6B7280', poesia: '#8B5CF6', festival: '#F97316',
  centro_cultural: '#3B82F6', cine: '#DC2626', circo: '#F97316',
  editorial: '#10B981', radio_comunitaria: '#06B6D4', filosofia: '#8B5CF6',
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

const MUNICIPIO_LABELS: Record<string, string> = {
  medellin: 'Medellín', bello: 'Bello', itagui: 'Itagüí', envigado: 'Envigado',
  sabaneta: 'Sabaneta', la_estrella: 'La Estrella', caldas: 'Caldas',
  copacabana: 'Copacabana', girardota: 'Girardota', barbosa: 'Barbosa',
}

// Center [lat, lng] + zoom for each municipality
const MUNICIPIO_VIEW: Record<string, [number, number, number]> = {
  medellin:   [6.2442, -75.5812, 13],
  bello:      [6.337,  -75.555,  13],
  itagui:     [6.184,  -75.599,  14],
  envigado:   [6.170,  -75.552,  14],
  sabaneta:   [6.151,  -75.619,  15],
  la_estrella:[6.156,  -75.644,  14],
  caldas:     [6.094,  -75.635,  14],
  copacabana: [6.353,  -75.502,  14],
  girardota:  [6.383,  -75.447,  14],
  barbosa:    [6.439,  -75.333,  14],
}

// IGAC/DIVIPOLA municipal codes → our key names (property: MpCodigo)
const DIVIPOLA_TO_KEY: Record<string, string> = {
  '05001': 'medellin', '05079': 'bello',    '05088': 'barbosa',
  '05129': 'caldas',   '05212': 'copacabana', '05266': 'envigado',
  '05308': 'girardota', '05360': 'itagui',   '05380': 'la_estrella',
  '05631': 'sabaneta',
}

// ── Map-control components ────────────────────────────────────────────────────
function FitBounds({ coords }: { coords: [number, number][] }) {
  const map = useMap()
  useEffect(() => {
    if (coords.length === 0) return
    if (coords.length === 1) { map.setView(coords[0], 14); return }
    const bounds = coords.reduce((b, c) => b.extend(c), map.getBounds().pad(-1))
    try { map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 }) } catch { /* ignore */ }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [coords.length])
  return null
}

function SetMunicipioView({ municipio }: { municipio: string | null }) {
  const map = useMap()
  useEffect(() => {
    if (!municipio) {
      map.setView([6.2442, -75.5812], 12)
      return
    }
    const v = MUNICIPIO_VIEW[municipio]
    if (v) map.setView([v[0], v[1]], v[2], { animate: true })
  }, [municipio, map])
  return null
}

// ── Main component ────────────────────────────────────────────────────────────
interface CulturalMapProps {
  zonaFilter?: string
  zonas?: Zona[]
}

export default function CulturalMap({ zonaFilter, zonas = [] }: CulturalMapProps = {}) {
  const [espacios, setEspacios] = useState<Espacio[]>([])
  const [eventos, setEventos] = useState<Evento[]>([])
  const [activeCats, setActiveCats] = useState<Set<string>>(new Set(ALL_CATS))
  const [showAllCats, setShowAllCats] = useState(false)
  const [showEquipamientos, setShowEquipamientos] = useState(true)
  const [showEventos, setShowEventos] = useState(true)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [geoSection, setGeoSection] = useState(true)
  const [catSection, setCatSection] = useState(true)

  // Geographic filter
  const [selectedMunicipio, setSelectedMunicipio] = useState<string | null>(null)
  const [selectedBarrio, setSelectedBarrio] = useState<string | null>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [municipioGeoJson, setMunicipioGeoJson] = useState<any>(null)

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

    // Fetch Valle de Aburrá municipality boundaries from IGAC ArcGIS Online (CORS OK, official data)
    const codes = Object.keys(DIVIPOLA_TO_KEY).map(c => `'${c}'`).join(',')
    const igacUrl = `https://services2.arcgis.com/RVvWzU3lgJISqdke/ArcGIS/rest/services/Municipio/FeatureServer/0/query?where=MpCodigo+IN+(${codes})&outFields=MpCodigo,MpNombre&outSR=4326&f=geojson`
    fetch(igacUrl)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data?.type === 'FeatureCollection') setMunicipioGeoJson(data) })
      .catch(() => {})
  }, [])

  // Municipio counts from data
  const municipioCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    espacios.forEach(e => {
      const key = normalizeKey(e.municipio)
      if (key) counts[key] = (counts[key] ?? 0) + 1
    })
    return counts
  }, [espacios])

  // Available barrios for selected municipio
  const barriosDisponibles = useMemo(() => {
    if (!selectedMunicipio) return []
    const b = espacios
      .filter(e => normalizeKey(e.municipio) === selectedMunicipio && e.barrio)
      .map(e => e.barrio as string)
    return Array.from(new Set(b)).sort((a, z) => a.localeCompare(z, 'es'))
  }, [espacios, selectedMunicipio])

  const filtered = useMemo(() =>
    espacios.filter(e => {
      const lat = e.lat ?? e.coordenadas?.lat
      const lng = e.lng ?? e.coordenadas?.lng
      if (!lat || !lng) return false
      if (e.es_equipamiento_publico && !showEquipamientos) return false
      if (!(activeCats.has(e.categoria_principal) || !ALL_CATS.includes(e.categoria_principal))) return false
      if (zonaActiva && !itemMatchesZona(e, zonaActiva)) return false
      if (selectedMunicipio && normalizeKey(e.municipio) !== selectedMunicipio) return false
      if (selectedBarrio && normalizeKey(e.barrio) !== normalizeKey(selectedBarrio)) return false
      return true
    }),
  [espacios, activeCats, showEquipamientos, zonaActiva, selectedMunicipio, selectedBarrio])

  const filteredEventos = useMemo(() =>
    eventos.filter(ev => {
      if (zonaActiva && !itemMatchesZona(ev, zonaActiva)) return false
      if (selectedMunicipio && normalizeKey(ev.municipio) !== selectedMunicipio) return false
      return true
    }),
  [eventos, zonaActiva, selectedMunicipio])

  const coords = useMemo<[number, number][]>(() => {
    if (selectedMunicipio) return [] // handled by SetMunicipioView
    const ec = filtered.map(e => [e.lat ?? e.coordenadas?.lat ?? 0, e.lng ?? e.coordenadas?.lng ?? 0] as [number, number])
    if (zonaActiva && filteredEventos.length > 0) {
      const evc = filteredEventos.filter(ev => ev.lat && ev.lng).map(ev => [ev.lat!, ev.lng!] as [number, number])
      return [...ec, ...evc]
    }
    return ec
  }, [filtered, filteredEventos, zonaActiva, selectedMunicipio])

  const toggleCat = (cat: string) => {
    setActiveCats(prev => { const n = new Set(prev); n.has(cat) ? n.delete(cat) : n.add(cat); return n })
  }

  const selectMunicipio = (key: string | null) => {
    setSelectedMunicipio(key)
    setSelectedBarrio(null)
  }

  const mainCats = ALL_CATS.slice(0, 8)
  const extraCats = ALL_CATS.slice(8)
  const espaciosConCoords = espacios.filter(e => (e.lat ?? e.coordenadas?.lat) && (e.lng ?? e.coordenadas?.lng)).length

  // GeoJSON style + click — IGAC property: MpCodigo, MpNombre
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const geoJsonStyle = (feature?: any) => {
    const code: string = feature?.properties?.MpCodigo ?? ''
    const key = DIVIPOLA_TO_KEY[code]
    const isSelected = key && key === selectedMunicipio
    return {
      color: isSelected ? '#F59E0B' : '#374151',
      weight: isSelected ? 2.5 : 1,
      fillOpacity: isSelected ? 0.08 : 0.03,
      fillColor: isSelected ? '#F59E0B' : '#374151',
      opacity: 0.6,
    }
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const onEachMunicipio = (feature: any, layer: any) => {
    const code: string = feature?.properties?.MpCodigo ?? ''
    const key = DIVIPOLA_TO_KEY[code]
    if (key) {
      layer.on('click', () => selectMunicipio(key === selectedMunicipio ? null : key))
      layer.bindTooltip((feature.properties?.MpNombre as string) ?? '', {
        permanent: false, direction: 'center',
        className: 'font-mono text-xs font-bold bg-white border border-black px-2 py-1',
      })
    }
  }

  const filterPanel = (
    <div className="p-3 h-full overflow-y-auto text-[11px] font-mono">

      {/* ── Geographic filter ─────────────────────── */}
      <button
        type="button"
        onClick={() => setGeoSection(v => !v)}
        className="flex items-center justify-between w-full font-black uppercase tracking-[0.15em] text-[10px] mb-2"
      >
        <span>📍 Área geográfica</span>
        <span>{geoSection ? '▲' : '▼'}</span>
      </button>

      {geoSection && (
        <div className="space-y-1 mb-3">
          {/* Breadcrumb */}
          {selectedMunicipio && (
            <div className="flex items-center gap-1 text-[9px] text-neutral-400 mb-2">
              <button onClick={() => selectMunicipio(null)} className="hover:text-black underline">
                Valle de Aburrá
              </button>
              <span>›</span>
              <span className="font-bold text-black">{MUNICIPIO_LABELS[selectedMunicipio] ?? selectedMunicipio}</span>
              {selectedBarrio && (
                <>
                  <span>›</span>
                  <span className="font-bold text-black">{selectedBarrio}</span>
                </>
              )}
            </div>
          )}

          {/* Municipality buttons */}
          {!selectedMunicipio ? (
            <div className="space-y-0.5">
              {Object.entries(MUNICIPIO_LABELS).map(([key, label]) => {
                const count = municipioCounts[key] ?? 0
                return (
                  <button
                    key={key}
                    onClick={() => selectMunicipio(key)}
                    className="flex items-center justify-between w-full px-2 py-1 hover:bg-yellow-50 hover:border-black border border-transparent text-left transition-colors"
                  >
                    <span>{label}</span>
                    {count > 0 && (
                      <span className="bg-black text-white text-[8px] px-1.5 py-0.5 font-bold">{count}</span>
                    )}
                  </button>
                )
              })}
            </div>
          ) : (
            <>
              <button
                onClick={() => selectMunicipio(null)}
                className="text-[9px] uppercase tracking-widest hover:underline text-neutral-500 mb-2 block"
              >
                ← Todo el Valle
              </button>

              {/* Barrio sub-filter */}
              {barriosDisponibles.length > 0 && (
                <div className="space-y-0.5 max-h-32 overflow-y-auto border border-neutral-200 p-1">
                  <button
                    onClick={() => setSelectedBarrio(null)}
                    className={`w-full text-left px-2 py-0.5 text-[9px] ${!selectedBarrio ? 'font-bold bg-yellow-100' : 'hover:bg-neutral-50'}`}
                  >
                    Todos los barrios
                  </button>
                  {barriosDisponibles.map(b => (
                    <button
                      key={b}
                      onClick={() => setSelectedBarrio(selectedBarrio === b ? null : b)}
                      className={`w-full text-left px-2 py-0.5 text-[9px] truncate ${selectedBarrio === b ? 'font-bold bg-yellow-100' : 'hover:bg-neutral-50'}`}
                    >
                      {b}
                    </button>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}

      <div className="border-t border-black/10 my-2" />

      {/* ── Category filter ───────────────────────── */}
      <button
        type="button"
        onClick={() => setCatSection(v => !v)}
        className="flex items-center justify-between w-full font-black uppercase tracking-[0.15em] text-[10px] mb-2"
      >
        <span>🎭 Tipo de lugar</span>
        <span>{catSection ? '▲' : '▼'}</span>
      </button>

      {catSection && (
        <div className="space-y-1 mb-3">
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
      )}

      <div className="border-t-2 border-black mt-2 pt-2 space-y-2">
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
        </div>
      )}

      <p className="text-[10px] font-mono font-black mt-3 pt-2 border-t border-black/10 uppercase tracking-wider">
        {filtered.length} / {espaciosConCoords} lugares
      </p>
    </div>
  )

  return (
    <div className="relative">
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

        {/* Municipality boundary overlay — only renders if DANE fetch succeeded */}
        {municipioGeoJson && (
          <GeoJSON
            key={selectedMunicipio ?? 'none'}
            data={municipioGeoJson}
            style={geoJsonStyle}
            onEachFeature={onEachMunicipio}
          />
        )}

        <FitBounds coords={coords} />
        <SetMunicipioView municipio={selectedMunicipio} />

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

      {/* Desktop: fixed left panel */}
      <div className="hidden sm:block absolute top-4 left-4 w-56 max-h-[75vh] bg-white/97 backdrop-blur-sm border-2 border-black z-[1000] shadow-sm">
        {filterPanel}
      </div>

      {/* Mobile: toggle button */}
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

      {/* Mobile: bottom sheet */}
      {filtersOpen && (
        <div className="sm:hidden absolute bottom-0 left-0 right-0 z-[1000] bg-white border-t-2 border-black max-h-[60vh] overflow-y-auto shadow-2xl">
          {filterPanel}
        </div>
      )}
    </div>
  )
}
