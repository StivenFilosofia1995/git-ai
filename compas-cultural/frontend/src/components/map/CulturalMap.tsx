import { useEffect, useRef, useState } from 'react'
import mapboxgl from 'mapbox-gl'
import 'mapbox-gl/dist/mapbox-gl.css'
import { getEspacios, type Espacio } from '../../lib/api'

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN

if (MAPBOX_TOKEN) {
  mapboxgl.accessToken = MAPBOX_TOKEN
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
}

const ALL_CATS = ['teatro', 'hip_hop', 'jazz', 'galeria', 'libreria', 'casa_cultura', 'electronica', 'danza']

export default function CulturalMap() {
  const mapContainer = useRef<HTMLDivElement>(null)
  const map = useRef<mapboxgl.Map | null>(null)
  const markersRef = useRef<mapboxgl.Marker[]>([])
  const [espacios, setEspacios] = useState<Espacio[]>([])
  const [activeCats, setActiveCats] = useState<Set<string>>(new Set(ALL_CATS))

  useEffect(() => {
    getEspacios({ limit: 200 }).then(setEspacios).catch(console.error)
  }, [])

  useEffect(() => {
    if (map.current) return

    if (!MAPBOX_TOKEN) {
      console.error('Mapbox token not found')
      return
    }

    map.current = new mapboxgl.Map({
      container: mapContainer.current!,
      style: 'mapbox://styles/mapbox/light-v11',
      center: [-75.5812, 6.2442],
      zoom: 12,
      maxZoom: 18,
      minZoom: 10
    })

    map.current.addControl(new mapboxgl.NavigationControl(), 'top-right')
    map.current.addControl(
      new mapboxgl.GeolocateControl({
        positionOptions: { enableHighAccuracy: true },
        trackUserLocation: true
      })
    )

    return () => {
      map.current?.remove()
    }
  }, [])

  useEffect(() => {
    if (!map.current) return

    // Remove existing markers
    markersRef.current.forEach(m => m.remove())
    markersRef.current = []

    const filtered = espacios.filter(e => {
      const lat = e.lat ?? e.coordenadas?.lat
      const lng = e.lng ?? e.coordenadas?.lng
      return lat && lng && activeCats.has(e.categoria_principal)
    })

    for (const espacio of filtered) {
      const lat = espacio.lat ?? espacio.coordenadas?.lat
      const lng = espacio.lng ?? espacio.coordenadas?.lng
      if (!lat || !lng) continue

      const color = CAT_MARKER_COLORS[espacio.categoria_principal] ?? '#6B7280'

      const el = document.createElement('div')
      el.className = 'cultural-marker'
      el.style.width = '12px'
      el.style.height = '12px'
      el.style.borderRadius = '50%'
      el.style.backgroundColor = color
      el.style.border = '2px solid white'
      el.style.boxShadow = '0 1px 3px rgba(0,0,0,0.3)'
      el.style.cursor = 'pointer'

      const popup = new mapboxgl.Popup({ offset: 15, closeButton: false })
        .setHTML(`
          <div style="font-family:'Space Mono',monospace;padding:4px 0">
            <div style="font-weight:700;font-size:12px;margin-bottom:2px">${espacio.nombre}</div>
            <div style="font-size:10px;color:#666;text-transform:uppercase;letter-spacing:0.5px">${espacio.categoria_principal.replace(/_/g, ' ')}</div>
            ${espacio.barrio ? `<div style="font-size:10px;color:#999;margin-top:2px">◉ ${espacio.barrio}, ${espacio.municipio}</div>` : ''}
          </div>
        `)

      const marker = new mapboxgl.Marker(el)
        .setLngLat([lng, lat])
        .setPopup(popup)
        .addTo(map.current)

      markersRef.current.push(marker)
    }
  }, [espacios, activeCats])

  const toggleCat = (cat: string) => {
    setActiveCats(prev => {
      const next = new Set(prev)
      if (next.has(cat)) next.delete(cat)
      else next.add(cat)
      return next
    })
  }

  const catLabels: Record<string, string> = {
    teatro: 'Teatro',
    hip_hop: 'Hip Hop',
    jazz: 'Jazz',
    galeria: 'Galerías',
    libreria: 'Librerías',
    casa_cultura: 'Casas Cultura',
    electronica: 'Electrónica',
    danza: 'Danza',
  }

  return (
    <div className="relative">
      <div ref={mapContainer} className="w-full h-[600px] border-2 border-black" />
      <div className="absolute top-4 left-4 bg-white border-2 border-black p-4">
        <h3 className="font-mono font-bold text-sm mb-2">FILTROS</h3>
        <div className="space-y-2">
          {ALL_CATS.map((cat) => (
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
        </div>
        <p className="text-[10px] font-mono font-bold mt-2 uppercase tracking-wider">{espacios.length} lugares</p>
      </div>
    </div>
  )
}