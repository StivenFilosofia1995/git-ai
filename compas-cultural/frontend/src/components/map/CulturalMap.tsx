import { useEffect, useMemo, useState } from 'react'
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { getEspacios, type Espacio } from '../../lib/api'

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
  const [activeCats, setActiveCats] = useState<Set<string>>(new Set(ALL_CATS))
  const [showAllCats, setShowAllCats] = useState(false)

  useEffect(() => {
    getEspacios({ limit: 500 }).then(setEspacios).catch(console.error)
  }, [])

  const filtered = useMemo(() =>
    espacios.filter(e => {
      const lat = e.lat ?? e.coordenadas?.lat
      const lng = e.lng ?? e.coordenadas?.lng
      if (!lat || !lng) return false
      return activeCats.has(e.categoria_principal) || !ALL_CATS.includes(e.categoria_principal)
    }),
  [espacios, activeCats])

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
        {filtered.map(espacio => {
          const lat = espacio.lat ?? espacio.coordenadas?.lat ?? 0
          const lng = espacio.lng ?? espacio.coordenadas?.lng ?? 0
          const color = CAT_MARKER_COLORS[espacio.categoria_principal] ?? '#6B7280'
          return (
            <CircleMarker
              key={espacio.id}
              center={[lat, lng]}
              radius={7}
              pathOptions={{
                fillColor: color,
                fillOpacity: 0.85,
                color: '#fff',
                weight: 2,
              }}
            >
              <Popup>
                <a
                  href={`/espacio/${espacio.slug}`}
                  style={{ textDecoration: 'none', color: 'inherit', display: 'block', fontFamily: "'Space Mono', monospace" }}
                >
                  <div style={{ fontWeight: 700, fontSize: 12, marginBottom: 2 }}>{espacio.nombre}</div>
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
      </MapContainer>

      {/* FILTERS panel */}
      <div className="absolute top-4 left-4 bg-white/95 backdrop-blur-sm border-2 border-black p-4 max-h-[560px] overflow-y-auto z-[1000]">
        <h3 className="font-mono font-bold text-sm mb-2">FILTROS</h3>
        <div className="space-y-2">
          {mainCats.map((cat) => (
            <label key={cat} className="flex items-center space-x-2 text-xs cursor-pointer">
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
            <label key={cat} className="flex items-center space-x-2 text-xs cursor-pointer">
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
        <p className="text-[10px] font-mono font-bold mt-2 uppercase tracking-wider">
          {espaciosConCoords} lugares
        </p>
      </div>
    </div>
  )
}