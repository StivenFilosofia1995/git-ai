import { useCallback, useEffect, useState } from 'react'
import EventCard from './EventCard'
import { getEventosCerca, type Evento } from '../../lib/api'

/**
 * "Cerca de mí" — distancias REALES calculadas en el servidor (/eventos/cerca),
 * con coordenadas del evento o heredadas de su espacio.
 * Si el usuario no comparte la ubicación, puede elegir su barrio/municipio:
 * nunca queda en un callejón sin salida.
 */

type Estado = 'idle' | 'ubicando' | 'cargando' | 'listo' | 'error'

interface Punto { lat: number; lng: number; nombre: string }

// Puntos de referencia aproximados (plaza principal / centro del barrio)
const PUNTOS: Punto[] = [
  { nombre: 'Medellín · Centro', lat: 6.2476, lng: -75.5658 },
  { nombre: 'El Poblado', lat: 6.2088, lng: -75.5672 },
  { nombre: 'Laureles · Estadio', lat: 6.2443, lng: -75.5906 },
  { nombre: 'Prado · Boston', lat: 6.2565, lng: -75.5605 },
  { nombre: 'Buenos Aires', lat: 6.2380, lng: -75.5530 },
  { nombre: 'Manrique · Aranjuez', lat: 6.2760, lng: -75.5530 },
  { nombre: 'Castilla · Robledo', lat: 6.2850, lng: -75.5850 },
  { nombre: 'Belén', lat: 6.2310, lng: -75.6040 },
  { nombre: 'Ciudad del Río', lat: 6.2230, lng: -75.5740 },
  { nombre: 'Envigado', lat: 6.1709, lng: -75.5872 },
  { nombre: 'Itagüí', lat: 6.1719, lng: -75.6110 },
  { nombre: 'Sabaneta', lat: 6.1515, lng: -75.6166 },
  { nombre: 'La Estrella', lat: 6.1576, lng: -75.6430 },
  { nombre: 'Bello', lat: 6.3373, lng: -75.5579 },
  { nombre: 'Copacabana', lat: 6.3486, lng: -75.5089 },
  { nombre: 'Caldas', lat: 6.0910, lng: -75.6360 },
]

const RADIOS = [1, 3, 5, 10, 20]
const STORAGE_KEY = 'eterea:ultima-ubicacion'

function leerUbicacionGuardada(): Punto | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const p = JSON.parse(raw) as Punto & { ts?: number }
    // Ubicación GPS: válida 30 min. Barrio elegido a mano: se recuerda siempre.
    if (p.nombre === 'Tu ubicación' && (!p.ts || Date.now() - p.ts > 30 * 60_000)) return null
    return p
  } catch {
    return null
  }
}

function guardarUbicacion(p: Punto) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...p, ts: Date.now() })) } catch { /* modo privado */ }
}

function mensajeGeoError(err: GeolocationPositionError): string {
  if (!window.isSecureContext) return 'La ubicación solo funciona en una conexión segura (https).'
  if (err.code === err.PERMISSION_DENIED) return 'No tenemos permiso para usar tu ubicación. Elige tu barrio abajo o actívala en los ajustes del navegador.'
  if (err.code === err.TIMEOUT) return 'Tu ubicación tardó demasiado. Intenta otra vez o elige tu barrio.'
  return 'No pudimos detectar tu ubicación. Elige tu barrio abajo.'
}

export default function CercaDeTi() {
  const [estado, setEstado] = useState<Estado>('idle')
  const [punto, setPunto] = useState<Punto | null>(() => leerUbicacionGuardada())
  const [radio, setRadio] = useState(5)
  const [dias, setDias] = useState<1 | 7>(7)
  const [eventos, setEventos] = useState<Evento[]>([])
  const [mensaje, setMensaje] = useState<string | null>(null)

  const buscar = useCallback(async (p: Punto, r: number, d: number) => {
    setEstado('cargando')
    setMensaje(null)
    try {
      const data = await getEventosCerca(p.lat, p.lng, r, d)
      setEventos(data)
      setEstado('listo')
    } catch {
      setMensaje('No pudimos cargar los eventos cercanos. Intenta de nuevo.')
      setEstado('error')
    }
  }, [])

  useEffect(() => {
    if (punto) void buscar(punto, radio, dias)
  }, [punto, radio, dias, buscar])

  // Si el permiso ya fue concedido antes, ubicar sin pedir nada (cero toques)
  useEffect(() => {
    if (punto || !navigator.permissions?.query) return
    navigator.permissions.query({ name: 'geolocation' as PermissionName })
      .then(res => { if (res.state === 'granted') usarMiUbicacion() })
      .catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function usarMiUbicacion() {
    if (!('geolocation' in navigator)) {
      setMensaje('Tu navegador no permite compartir ubicación. Elige tu barrio abajo.')
      setEstado('error')
      return
    }
    setEstado('ubicando')
    setMensaje(null)
    navigator.geolocation.getCurrentPosition(
      pos => {
        const p = { lat: pos.coords.latitude, lng: pos.coords.longitude, nombre: 'Tu ubicación' }
        guardarUbicacion(p)
        setPunto(p)
      },
      err => {
        setMensaje(mensajeGeoError(err))
        setEstado('error')
      },
      { enableHighAccuracy: false, timeout: 12_000, maximumAge: 5 * 60_000 },
    )
  }

  function elegirPunto(nombre: string) {
    const p = PUNTOS.find(x => x.nombre === nombre)
    if (!p) return
    guardarUbicacion(p)
    setPunto(p)
  }

  const cargando = estado === 'ubicando' || estado === 'cargando'

  return (
    <div className="space-y-4">
      {/* Controles */}
      <div className="border-2 border-black p-3 sm:p-4 space-y-3">
        <div className="flex flex-col sm:flex-row gap-2">
          <button
            onClick={usarMiUbicacion}
            disabled={estado === 'ubicando'}
            className="min-h-[48px] px-5 bg-black text-white font-bold text-base border-2 border-black hover:bg-white hover:text-black transition-colors disabled:opacity-60"
          >
            {estado === 'ubicando' ? 'Ubicando…' : '📍 Usar mi ubicación'}
          </button>
          <label className="flex-1">
            <span className="sr-only">O elige tu barrio</span>
            <select
              value={punto && punto.nombre !== 'Tu ubicación' ? punto.nombre : ''}
              onChange={e => elegirPunto(e.target.value)}
              className="w-full min-h-[48px] px-3 text-base border-2 border-black bg-white"
            >
              <option value="">…o elige tu barrio / municipio</option>
              {PUNTOS.map(p => <option key={p.nombre} value={p.nombre}>{p.nombre}</option>)}
            </select>
          </label>
        </div>

        {punto && (
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
            <span>Cerca de: <strong>{punto.nombre}</strong></span>
            <span className="flex items-center gap-1" role="group" aria-label="Radio de búsqueda">
              <span className="text-black/60 mr-1">a menos de</span>
              {RADIOS.map(r => (
                <button
                  key={r}
                  onClick={() => setRadio(r)}
                  aria-pressed={radio === r}
                  className={`min-w-[44px] min-h-[36px] px-2 border-2 border-black font-bold ${radio === r ? 'bg-black text-white' : 'bg-white'}`}
                >
                  {r} km
                </button>
              ))}
            </span>
            <span className="flex items-center gap-1" role="group" aria-label="Cuándo">
              {([1, 7] as const).map(d => (
                <button
                  key={d}
                  onClick={() => setDias(d)}
                  aria-pressed={dias === d}
                  className={`min-h-[36px] px-3 border-2 border-black font-bold ${dias === d ? 'bg-black text-white' : 'bg-white'}`}
                >
                  {d === 1 ? 'Hoy' : '7 días'}
                </button>
              ))}
            </span>
          </div>
        )}
      </div>

      {mensaje && (
        <p role="alert" className="border-2 border-black bg-[#FEF3C7] p-3 text-sm">{mensaje}</p>
      )}

      {cargando && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4" aria-busy="true">
          {[1, 2, 3].map(k => <div key={k} className="border-2 border-black h-72 bg-black/5 motion-safe:animate-pulse" />)}
        </div>
      )}

      {estado === 'listo' && eventos.length === 0 && (
        <div className="border-2 border-dashed border-black p-6 text-center space-y-3">
          <p className="font-bold">No encontramos planes a menos de {radio} km{dias === 1 ? ' hoy' : ' esta semana'}.</p>
          <div className="flex justify-center gap-2 flex-wrap">
            {radio < 20 && (
              <button onClick={() => setRadio(RADIOS.find(r => r > radio) ?? 20)} className="min-h-[44px] px-4 border-2 border-black font-bold hover:bg-black hover:text-white">
                Ampliar a {RADIOS.find(r => r > radio) ?? 20} km
              </button>
            )}
            {dias === 1 && (
              <button onClick={() => setDias(7)} className="min-h-[44px] px-4 border-2 border-black font-bold hover:bg-black hover:text-white">
                Ver los próximos 7 días
              </button>
            )}
          </div>
        </div>
      )}

      {estado === 'listo' && eventos.length > 0 && (
        <>
          <p className="text-sm text-black/60">
            {eventos.length} plan{eventos.length === 1 ? '' : 'es'} ordenados por distancia
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {eventos.map(ev => <EventCard key={ev.id} evento={ev} />)}
          </div>
        </>
      )}
    </div>
  )
}
