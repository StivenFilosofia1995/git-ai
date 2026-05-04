import { useState } from 'react'
import EventCard from './EventCard'
import {
  getEventosTodos,
  type Evento,
} from '../../lib/api'

// ─── Haversine (km) ──────────────────────────────────────────────────────────
function haversineKm(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const R = 6371
  const dLat = ((lat2 - lat1) * Math.PI) / 180
  const dLng = ((lng2 - lng1) * Math.PI) / 180
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLng / 2) ** 2
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

// Coordenadas aproximadas de los municipios del Valle de Aburrá
const MUNICIPIO_COORDS: Record<string, { lat: number; lng: number }> = {
  medellin: { lat: 6.2442, lng: -75.5812 },
  medellín: { lat: 6.2442, lng: -75.5812 },
  envigado: { lat: 6.1752, lng: -75.5928 },
  itagui: { lat: 6.1848, lng: -75.5990 },
  itagüí: { lat: 6.1848, lng: -75.5990 },
  bello: { lat: 6.3352, lng: -75.5574 },
  sabaneta: { lat: 6.1514, lng: -75.6165 },
  la_estrella: { lat: 6.1566, lng: -75.6425 },
  'la estrella': { lat: 6.1566, lng: -75.6425 },
  copacabana: { lat: 6.3494, lng: -75.5090 },
  caldas: { lat: 6.0944, lng: -75.6362 },
  girardota: { lat: 6.3783, lng: -75.4491 },
}



export default function CercaDeTi() {
  const [geoState, setGeoState] = useState<GeoState>('idle')
  const [geoError, setGeoError] = useState<string | null>(null)
  const [lat, setLat] = useState<number | null>(null)
  const [lng, setLng] = useState<number | null>(null)
  const [radioKm, setRadioKm] = useState(5)
  const [eventosProximos, setEventosProximos] = useState<(Evento & { distKm: number })[]>([])

  const buscarCerca = async (userLat: number, userLng: number, radio: number) => {
    setGeoState('loading')
    setEventosProximos([])

    try {
      const eventosData = await getEventosTodos({ municipio: undefined, maxRows: 500 })

      // Use Bogotá timezone for today's date
      const hoyStr = new Date().toLocaleDateString('en-CA', { timeZone: 'America/Bogota' })
      // Also include next 7 days so we have more events to show
      const en7dias = new Date()
      en7dias.setDate(en7dias.getDate() + 7)
      const en7diasStr = en7dias.toLocaleDateString('en-CA', { timeZone: 'America/Bogota' })

      const conDistancia = eventosData
        .filter(e => {
          const fechaInicio = e.fecha_inicio?.slice(0, 10) ?? ''
          const fechaFin = e.fecha_fin?.slice(0, 10) ?? fechaInicio
          // Eventos de hoy, en curso o próximos 7 días
          return fechaInicio <= en7diasStr && (fechaFin >= hoyStr || fechaInicio >= hoyStr)
        })
        .map(e => {
          // Primero intentar coordenadas exactas del evento
          if (e.lat != null && e.lng != null) {
            return { ...e, distKm: haversineKm(userLat, userLng, e.lat, e.lng) }
          }
          // Fallback: coordenadas aproximadas del municipio
          const muni = (e.municipio ?? '').toLowerCase().trim()
          const muniCoords = MUNICIPIO_COORDS[muni]
          if (muniCoords) {
            return { ...e, distKm: haversineKm(userLat, userLng, muniCoords.lat, muniCoords.lng) }
          }
          return null
        })
        .filter((e): e is (typeof eventosData[0] & { distKm: number }) => e !== null && e.distKm <= radio)
        .sort((a, b) => a.distKm - b.distKm)
        .slice(0, 20)

      setEventosProximos(conDistancia)
      setGeoState('done')
    } catch {
      setGeoError('No fue posible cargar eventos de tu zona.')
      setGeoState('error')
    }
  }

  const handleUbicarme = () => {
    if (!navigator.geolocation) {
      setGeoError('Tu navegador no soporta geolocalización.')
      setGeoState('error')
      return
    }
    setGeoState('loading')
    setGeoError(null)
    navigator.geolocation.getCurrentPosition(
      pos => {
        const { latitude, longitude } = pos.coords
        setLat(latitude)
        setLng(longitude)
        void buscarCerca(latitude, longitude, radioKm)
      },
      err => {
        setGeoError(
          err.code === 1
            ? 'Permiso de ubicación denegado. Habilitalo en tu navegador.'
            : 'No se pudo obtener tu ubicación. Intentá de nuevo.',
        )
        setGeoState('error')
      },
      { timeout: 10000, maximumAge: 60000 },
    )
  }


  const hayResultados = eventosProximos.length > 0

  return (
    <section id="cerca-de-ti" className="border-2 border-black mb-10 scroll-mt-24">
      {/* Header */}
      <div className="border-b-2 border-black px-5 py-4 flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <span className="w-4 h-4 bg-black rounded-full animate-pulse" />
          <h2 className="text-lg font-heading font-black uppercase tracking-wider">CERCA DE TI</h2>
          <span className="text-[9px] font-mono font-bold opacity-50 uppercase tracking-wider">
            Eventos de hoy en tu zona
          </span>
        </div>

        {geoState === 'idle' || geoState === 'error' ? (
          <button
            onClick={handleUbicarme}
            className="px-4 py-2 text-[10px] font-mono font-bold uppercase tracking-wider border-2 border-black bg-black text-white hover:bg-neutral-800 transition-all flex items-center gap-2"
          >
            📍 Usar mi ubicación
          </button>
        ) : geoState === 'loading' ? (
          <span className="text-[10px] font-mono font-bold opacity-60 flex items-center gap-2">
            <span className="w-3 h-3 border-2 border-black border-t-transparent rounded-full animate-spin inline-block" />
            Buscando...
          </span>
        ) : (
          <div className="flex items-center gap-3">
            <label className="text-[10px] font-mono font-bold opacity-60 flex items-center gap-1.5">
              Radio:
              <select
                value={radioKm}
                onChange={e => {
                  const r = Number(e.target.value)
                  setRadioKm(r)
                  if (lat != null && lng != null) void buscarCerca(lat, lng, r)
                }}
                className="border border-black px-1 py-0.5 text-[10px] font-mono bg-white"
              >
                <option value={1}>1 km</option>
                <option value={3}>3 km</option>
                <option value={5}>5 km</option>
                <option value={10}>10 km</option>
              </select>
            </label>
            <button
              onClick={handleUbicarme}
              className="px-3 py-1 text-[9px] font-mono font-bold uppercase tracking-wider border border-black hover:bg-black hover:text-white transition-all"
            >
              Actualizar
            </button>
          </div>
        )}
      </div>

      {/* Error */}
      {geoError && (
        <div className="px-5 py-3 text-[11px] font-mono border-b border-black/20 bg-red-50">
          {geoError}
        </div>
      )}

      {/* Idle state */}
      {geoState === 'idle' && (
        <div className="px-5 py-12 text-center">
          <div className="text-4xl mb-3">📍</div>
          <p className="text-sm font-mono opacity-60 max-w-sm mx-auto">
            Compartí tu ubicación y te mostramos los eventos culturales de hoy a menos de {radioKm} km de vos.
          </p>
        </div>
      )}

      {/* Loading skeleton */}
      {geoState === 'loading' && (
        <div className="px-5 py-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 3 }, (_, i) => (
            <div key={i} className="animate-pulse border border-black h-48" />
          ))}
        </div>
      )}

      {/* Results */}
      {geoState === 'done' && (
        <div className="px-5 py-6">
          {!hayResultados && (
            <p className="text-sm font-mono opacity-60 text-center py-8">
              No encontramos eventos de hoy con coordenadas a {radioKm} km de tu ubicación. Probá aumentar el radio.
            </p>
          )}

          {/* Eventos cercanos */}
          {eventosProximos.length > 0 && (
            <div className="mb-8">
              <div className="flex items-center gap-3 mb-4">
                <span className="w-3 h-3 bg-red-500 animate-pulse" />
                <h3 className="text-sm font-heading font-black uppercase tracking-wider">
                  Eventos de hoy cerca de ti
                </h3>
                <span className="text-[9px] font-mono font-bold opacity-50">
                  {eventosProximos.length} a menos de {radioKm} km
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {eventosProximos.map(ev => (
                  <div key={ev.id} className="relative">
                    <EventCard evento={ev} />
                    <div className="absolute top-2 right-2 bg-black text-white text-[8px] font-mono font-bold px-1.5 py-0.5 z-10">
                      {ev.distKm < 1
                        ? `${Math.round(ev.distKm * 1000)} m`
                        : `${ev.distKm.toFixed(1)} km`}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
