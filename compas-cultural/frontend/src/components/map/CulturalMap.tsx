import { useEffect, useMemo, useState } from 'react'
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet'
import MarkerClusterGroup from '@changey/react-leaflet-markercluster'
import 'leaflet/dist/leaflet.css'
import '@changey/react-leaflet-markercluster/dist/styles.min.css'
import { getEspacios, getEventosTodos, type Espacio, type Evento } from '../../lib/api'

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
  teatro: 'Teatro',
  hip_hop: 'Hip Hop',
  jazz: 'Jazz',
  galeria: 'Galerías',
  libreria: 'Librerías',
  casa_cultura: 'Casas Cultura',
  electronica: 'Electrónica',
  danza: 'Danza',
  arte_contemporaneo: 'Arte Contemporáneo',
  centro_cultural: 'Centros Culturales',
  musica_en_vivo: 'Música en Vivo',
  muralismo: 'Muralismo',
  fotografia: 'Fotografía',
  batalla_freestyle: 'Freestyle',
  poesia: 'Poesía',
  festival: 'Festivales',
  espacio_hibrido: 'Espacio Híbrido',
  cine: 'Cine',
}

/** Fit map bounds to visible markers */
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

export default function CulturalMap() {
  const [espacios, setEspacios] = useState<Espacio[]>([])
  const [eventos, setEventos] = useState<Evento[]>([])
  const [activeCats, setActiveCats] = useState<Set<string>>(new Set(ALL_CATS))
  const [showAllCats, setShowAllCats] = useState(false)
  const [showEquipamientos, setShowEquipamientos] = useState(true)
  const [showEventos, setShowEventos] = useState(true)

  useEffect(() => {
    getEspacios({ limit: 1000 }).then(setEspacios).catch(console.error)
    // Load events with coordinates (today + next 7 days)
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
      return activeCats.has(e.categoria_principal) || !ALL_CATS.includes(e.categoria_principal)
    }),
  [espacios, activeCats, showEquipamientos])

  const coords = useMemo<[number, number][]>(() =>
    filtered.map(e => [e.lat ?? e.coordenadas?.lat ?? 0, e.lng ?? e.coordenadas?.lng ?? 0]),
  [filtered])

  const toggleCat = (cat: string) => {
    setActiveCats(prev => {
      const next = new Set(prev)
      if (next.has(cat)) next.delete(cat)
      else next.add(cat)
      return next
    })
  }

  const mainCats = ALL_CATS.slice(0, 8)
  const extraCats = ALL_CATS.slice(8)

  const espaciosConCoords = espacios.filter(e => {
    const lat = e.lat ?? e.coordenadas?.lat
    const lng = e.lng ?? e.coordenadas?.lng
    return lat && lng
  }).length

  return (
    <div className="relative">
      <MapContainer
        center={[6.2442, -75.5812]}
        zoom={12}
        minZoom={10}
        maxZoom={18}
        scrollWheelZoom
        className="w-full h-[600px] z-0"
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
                fillColor: color,
                fillOpacity: isPublico ? 0.95 : 0.85,
                color: isPublico ? '#000' : '#fff',
                weight: isPublico ? 2.5 : 2,
                dashArray: isPublico ? '4 2' : undefined,
              }}
            >
              <Popup>
                <a
                  href={`/espacio/${espacio.slug}`}
                  style={{ textDecoration: 'none', color: 'inherit', display: 'block', fontFamily: "'Space Mono', monospace" }}
                >
                  <div style={{ fontWeight: 700, fontSize: 12, marginBottom: 2 }}>
                    {isPublico && <span title="Equipamiento público">★ </span>}{espacio.nombre}
                  </div>
                  <div style={{ fontSize: 10, color: '#666', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                    {espacio.categoria_principal.replace(/_/g, ' ')}
                  </div>
                  {espacio.barrio && (
                    <div style={{ fontSize: 10, color: '#999', marginTop: 2 }}>
                      ◉ {espacio.barrio}, {espacio.municipio}
                    </div>
                  )}
                  <div style={{ fontSize: 9, color: '#000', marginTop: 4, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px' }}>
                    Ver detalle →
                  </div>
                </a>
              </Popup>
            </CircleMarker>
          )
        })}
        </MarkerClusterGroup>

        {/* Events layer — upcoming events with coordinates */}
        {showEventos && (
          <MarkerClusterGroup chunkedLoading>
            {eventos.map(ev => {
              const lat = ev.lat ?? 0
              const lng = ev.lng ?? 0
              const fecha = ev.fecha_inicio?.slice(0, 10) ?? ''
              const esHoy = fecha === new Date().toISOString().slice(0, 10)
              return (
                <CircleMarker
                  key={ev.id}
                  center={[lat, lng]}
                  radius={esHoy ? 9 : 6}
                  pathOptions={{
                    fillColor: esHoy ? '#EF4444' : '#F97316',
                    fillOpacity: 0.9,
                    color: '#fff',
                    weight: esHoy ? 2 : 1.5,
                  }}
                >
                  <Popup>
                    <a
                      href={`/evento/${ev.slug}`}
                      style={{ textDecoration: 'none', color: 'inherit', display: 'block', fontFamily: "'Space Mono', monospace", maxWidth: 200 }}
                    >
                      {esHoy && (
                        <div style={{ fontSize: 9, fontWeight: 700, color: '#EF4444', textTransform: 'uppercase', marginBottom: 2 }}>
                          ● HOY
                        </div>
                      )}
                      <div style={{ fontWeight: 700, fontSize: 12, marginBottom: 2, lineHeight: 1.3 }}>{ev.titulo}</div>
                      <div style={{ fontSize: 10, color: '#666' }}>{fecha}</div>
                      {ev.nombre_lugar && (
                        <div style={{ fontSize: 10, color: '#999', marginTop: 2 }}>◉ {ev.nombre_lugar}</div>
                      )}
                      {ev.es_gratuito && (
                        <div style={{ fontSize: 9, fontWeight: 700, color: '#10B981', marginTop: 2 }}>GRATIS</div>
                      )}
                      <div style={{ fontSize: 9, color: '#000', marginTop: 4, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1px' }}>
                        Ver evento →
                      </div>
                    </a>
                  </Popup>
                </CircleMarker>
              )
            })}
          </MarkerClusterGroup>
        )}
      </MapContainer>

      {/* FILTERS panel */}
      <div className="absolute top-4 left-4 bg-white/95 backdrop-blur-sm border-2 border-black p-4 max-h-[560px] overflow-y-auto z-[1000]">
        <h3 className="font-mono font-bold text-sm mb-2">FILTROS</h3>
        <div className="space-y-2">
          {mainCats.map((cat) => (
            <label key={cat} className="flex items-center gap-2 text-xs cursor-pointer">
              <input
                type="checkbox"
                className="rounded"
                checked={activeCats.has(cat)}
                onChange={() => toggleCat(cat)}
              />
              <span
                className="w-2 h-2 rounded-full inline-block"
                style={{ backgroundColor: CAT_MARKER_COLORS[cat] }}
              />
              <span>{catLabels[cat] ?? cat}</span>
            </label>
          ))}
          {showAllCats && extraCats.map((cat) => (
            <label key={cat} className="flex items-center gap-2 text-xs cursor-pointer">
              <input
                type="checkbox"
                className="rounded"
                checked={activeCats.has(cat)}
                onChange={() => toggleCat(cat)}
              />
              <span
                className="w-2 h-2 rounded-full inline-block"
                style={{ backgroundColor: CAT_MARKER_COLORS[cat] ?? '#6B7280' }}
              />
              <span>{catLabels[cat] ?? cat}</span>
            </label>
          ))}
          {extraCats.length > 0 && (
            <button
              type="button"
              onClick={() => setShowAllCats(v => !v)}
              className="text-[10px] font-mono font-bold uppercase tracking-wider hover:underline"
            >
              {showAllCats ? '▲ Menos' : `▼ +${extraCats.length} más`}
            </button>
          )}
        </div>
        <div className="border-t-2 border-black mt-3 pt-3">
          <label className="flex items-center gap-2 text-xs cursor-pointer">
            <input
              type="checkbox"
              className="rounded"
              checked={showEquipamientos}
              onChange={() => setShowEquipamientos(v => !v)}
            />
            <span className="font-bold">★ Equipamientos Públicos</span>
          </label>
          <p className="text-[9px] font-mono opacity-50 mt-1">UVAs · Bibliotecas · Teatros oficiales</p>
        </div>
        <div className="border-t border-black/20 mt-3 pt-3">
          <label className="flex items-center gap-2 text-xs cursor-pointer">
            <input
              type="checkbox"
              className="rounded"
              checked={showEventos}
              onChange={() => setShowEventos(v => !v)}
            />
            <span className="inline-flex items-center gap-1.5 font-bold">
              <span className="w-2.5 h-2.5 rounded-full bg-red-500 inline-block" />
              Eventos próximos
            </span>
          </label>
          <p className="text-[9px] font-mono opacity-50 mt-1">Hoy y los próximos 7 días</p>
          {showEventos && eventos.length > 0 && (
            <p className="text-[9px] font-mono font-bold mt-0.5">{eventos.length} eventos en el mapa</p>
          )}
        </div>
        <p className="text-[10px] font-mono font-bold mt-2 uppercase tracking-wider">
          {espaciosConCoords} lugares
        </p>
      </div>
    </div>
  )
}