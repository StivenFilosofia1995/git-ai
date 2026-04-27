import { useState } from 'react'
import { Link } from 'react-router-dom'
import EventCard from './EventCard'
import {
  getEspacios,
  getEventosTodos,
  discoverEventosAI,
  commitEventosDescubiertos,
  type Evento,
  type Espacio,
  type DescubiertoEvento,
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

type GeoState = 'idle' | 'loading' | 'done' | 'error'

export default function CercaDeTi() {
  const [geoState, setGeoState] = useState<GeoState>('idle')
  const [geoError, setGeoError] = useState<string | null>(null)
  const [lat, setLat] = useState<number | null>(null)
  const [lng, setLng] = useState<number | null>(null)
  const [radioKm, setRadioKm] = useState(5)
  const [eventosProximos, setEventosProximos] = useState<(Evento & { distKm: number })[]>([])
  const [espaciosProximos, setEspaciosProximos] = useState<(Espacio & { distKm: number })[]>([])
  const [webCandidatos, setWebCandidatos] = useState<DescubiertoEvento[]>([])
  const [webMsg, setWebMsg] = useState<string | null>(null)
  const [committing, setCommitting] = useState(false)
  const [commitMsg, setCommitMsg] = useState<string | null>(null)

  const buscarCerca = async (userLat: number, userLng: number, radio: number) => {
    setGeoState('loading')
    setEventosProximos([])
    setEspaciosProximos([])
    setWebCandidatos([])
    setWebMsg(null)
    setCommitMsg(null)

    try {
      const [espaciosData, eventosData, webRes] = await Promise.allSettled([
        getEspacios({ limit: 500 }),
        getEventosTodos({ municipio: undefined, maxRows: 200 }),
        discoverEventosAI({
          texto: 'eventos culturales cerca barrio Medellín',
          municipio: 'Medellín',
          max_queries: 3,
          max_results_per_query: 6,
          days_from: 0,
          days_ahead: 60,
          auto_insert: false,
        }),
      ])

      if (espaciosData.status === 'fulfilled') {
        const conCoordenadas = espaciosData.value
          .filter(e => e.lat != null && e.lng != null)
          .map(e => ({
            ...e,
            distKm: haversineKm(userLat, userLng, e.lat!, e.lng!),
          }))
          .filter(e => e.distKm <= radio)
          .sort((a, b) => a.distKm - b.distKm)
          .slice(0, 10)
        setEspaciosProximos(conCoordenadas)
      }

      if (eventosData.status === 'fulfilled') {
        const hoyIso = new Date().toISOString()
        const conCoordenadas = eventosData.value
          .filter(e => e.lat != null && e.lng != null && e.fecha_inicio >= hoyIso)
          .map(e => ({
            ...e,
            distKm: haversineKm(userLat, userLng, e.lat!, e.lng!),
          }))
          .filter(e => e.distKm <= radio)
          .sort((a, b) => a.distKm - b.distKm)
          .slice(0, 8)
        setEventosProximos(conCoordenadas)
      }

      if (webRes.status === 'fulfilled') {
        const found = webRes.value.result?.candidatos ?? []
        if (found.length > 0) {
          setWebCandidatos(found)
          setWebMsg(`La IA encontró ${found.length} evento(s) en la web cerca de tu zona`)
        }
      }

      setGeoState('done')
    } catch {
      setGeoError('No fue posible cargar datos de tu zona.')
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

  const handleCommit = async () => {
    if (webCandidatos.length === 0 || committing) return
    setCommitting(true)
    setCommitMsg(null)
    try {
      const res = await commitEventosDescubiertos(webCandidatos)
      setCommitMsg(res.message)
      setWebCandidatos([])
    } catch {
      setCommitMsg('Error al guardar. Intentá de nuevo.')
    } finally {
      setCommitting(false)
    }
  }

  const hayResultados = eventosProximos.length > 0 || espaciosProximos.length > 0

  return (
    <section className="border-2 border-black mb-10">
      {/* Header */}
      <div className="border-b-2 border-black px-5 py-4 flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <span className="w-4 h-4 bg-black rounded-full animate-pulse" />
          <h2 className="text-lg font-heading font-black uppercase tracking-wider">CERCA DE TI</h2>
          <span className="text-[9px] font-mono font-bold opacity-50 uppercase tracking-wider">
            Eventos y espacios en tu zona
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
            Compartí tu ubicación y te mostramos eventos, teatros, galerías y espacios culturales a menos de {radioKm} km de vos.
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
              No encontramos eventos con coordenadas a {radioKm} km de tu ubicación. Probá aumentar el radio.
            </p>
          )}

          {/* Eventos cercanos */}
          {eventosProximos.length > 0 && (
            <div className="mb-8">
              <div className="flex items-center gap-3 mb-4">
                <span className="w-3 h-3 bg-red-500 animate-pulse" />
                <h3 className="text-sm font-heading font-black uppercase tracking-wider">
                  Eventos cercanos
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

          {/* Espacios cercanos */}
          {espaciosProximos.length > 0 && (
            <div className="mb-6">
              <div className="flex items-center gap-3 mb-4">
                <span className="w-3 h-3 bg-black" />
                <h3 className="text-sm font-heading font-black uppercase tracking-wider">
                  Espacios culturales cercanos
                </h3>
                <span className="text-[9px] font-mono font-bold opacity-50">
                  {espaciosProximos.length} a menos de {radioKm} km
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-0 border-2 border-black">
                {espaciosProximos.map((esp, i) => (
                  <div
                    key={esp.id}
                    className="group border-b border-r border-black p-4 hover:bg-black hover:text-white transition-all relative"
                  >
                    <Link to={`/espacio/${esp.slug}`} className="absolute inset-0 z-10" />
                    <div className="flex justify-between items-start mb-2">
                      <span className="text-[9px] font-mono font-bold opacity-30 group-hover:opacity-100">
                        {String(i + 1).padStart(2, '0')}
                      </span>
                      <span className="text-[9px] font-mono font-bold bg-black text-white group-hover:bg-white group-hover:text-black px-1.5 py-0.5">
                        {esp.distKm < 1
                          ? `${Math.round(esp.distKm * 1000)} m`
                          : `${esp.distKm.toFixed(1)} km`}
                      </span>
                    </div>
                    <h4 className="font-heading font-black text-sm uppercase tracking-wide leading-tight mb-1">
                      {esp.nombre}
                    </h4>
                    {esp.descripcion_corta && (
                      <p className="text-[10px] font-mono opacity-50 group-hover:opacity-80 line-clamp-2 mb-2">
                        {esp.descripcion_corta}
                      </p>
                    )}
                    <div className="text-[9px] font-mono opacity-50 group-hover:opacity-100">
                      {esp.barrio && <span>◉ {esp.barrio} · </span>}
                      <span>{esp.municipio}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Web candidates */}
          {webMsg && (
            <div className="border border-black/30 p-4 bg-neutral-50 mt-4">
              <p className="text-[11px] font-mono mb-3">{webMsg}</p>
              {webCandidatos.length > 0 && (
                <>
                  <ul className="space-y-1 mb-3">
                    {webCandidatos.slice(0, 5).map((c, i) => (
                      <li key={i} className="text-[10px] font-mono">
                        <span className="font-bold">·</span> {c.titulo} — {c.fecha_inicio?.slice(0, 10) ?? 'fecha por confirmar'}
                      </li>
                    ))}
                  </ul>
                  <button
                    onClick={() => void handleCommit()}
                    disabled={committing}
                    className="px-4 py-2 text-[10px] font-mono font-bold uppercase tracking-wider border-2 border-black bg-black text-white hover:bg-neutral-800 transition-all disabled:opacity-40"
                  >
                    {committing ? 'Guardando...' : `Agregar ${webCandidatos.length} evento(s) a la agenda`}
                  </button>
                </>
              )}
              {commitMsg && (
                <p className="text-[10px] font-mono mt-2 text-green-700 font-bold">{commitMsg}</p>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  )
}
