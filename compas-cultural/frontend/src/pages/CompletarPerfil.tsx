import { useState, useEffect } from 'react'
import { Helmet } from 'react-helmet-async'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/AuthContext'
import { crearPerfil, getZonas, CATEGORIAS_CULTURALES, type Zona } from '../lib/api'

export default function CompletarPerfil() {
  const { user, marcarPerfilCompleto } = useAuth()
  const navigate = useNavigate()

  // Pre-fill from Google metadata
  const googleName = user?.user_metadata?.full_name ?? ''
  const googleAvatar = user?.user_metadata?.avatar_url ?? ''
  const parts = googleName.split(' ')

  const [nombre, setNombre] = useState(parts[0] ?? '')
  const [apellido, setApellido] = useState(parts.slice(1).join(' ') ?? '')
  const [telefono, setTelefono] = useState('')
  const [bio, setBio] = useState('')
  const [barrio, setBarrio] = useState('')
  const [preferencias, setPreferencias] = useState<string[]>([])
  const [zonaId, setZonaId] = useState<number | null>(null)
  const [zonas, setZonas] = useState<Zona[]>([])
  const [ubicacion, setUbicacion] = useState<{ lat: number; lng: number } | null>(null)
  const [geoLoading, setGeoLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    getZonas().then(setZonas).catch(() => {})
  }, [])

  const togglePref = (cat: string) => {
    setPreferencias(prev =>
      prev.includes(cat) ? prev.filter(p => p !== cat) : [...prev, cat]
    )
  }

  const pedirUbicacion = () => {
    if (!navigator.geolocation) return
    setGeoLoading(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setUbicacion({ lat: pos.coords.latitude, lng: pos.coords.longitude })
        setGeoLoading(false)
      },
      () => setGeoLoading(false),
      { enableHighAccuracy: true, timeout: 8000 }
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!user) return

    if (!nombre.trim() || !apellido.trim()) {
      setError('Nombre y apellido son obligatorios')
      return
    }

    setError(null)
    setLoading(true)

    try {
      await crearPerfil({
        nombre: nombre.trim(),
        apellido: apellido.trim(),
        email: user.email ?? '',
        preferencias,
        zona_id: zonaId ?? undefined,
        telefono: telefono.trim() || undefined,
        bio: bio.trim() || undefined,
        ubicacion_barrio: barrio.trim() || undefined,
        ubicacion_lat: ubicacion?.lat,
        ubicacion_lng: ubicacion?.lng,
      }, user.id)

      marcarPerfilCompleto()
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al crear perfil')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <Helmet>
        <title>Completar Perfil — Cultura ETÉREA</title>
      </Helmet>

      <div className="max-w-md mx-auto px-6 py-16">
        <div className="text-center mb-10">
          {googleAvatar && (
            <img
              src={googleAvatar}
              alt="Foto de perfil"
              className="w-20 h-20 rounded-full border-2 border-black mx-auto mb-4 object-cover"
              referrerPolicy="no-referrer"
            />
          )}
          {!googleAvatar && (
            <div className="w-20 h-20 bg-black flex items-center justify-center mx-auto mb-4 rounded-full">
              <span className="text-white font-heading font-bold text-2xl">
                {nombre.charAt(0).toUpperCase() || 'U'}
              </span>
            </div>
          )}
          <h1 className="text-2xl font-heading font-black tracking-tight mb-1 uppercase">
            Completá tu perfil
          </h1>
          <p className="text-sm font-mono uppercase tracking-wider">
            Contanos más sobre vos para personalizar tu experiencia
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Nombre y Apellido */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-mono font-bold uppercase tracking-wider mb-1.5">
                Nombre
              </label>
              <input
                type="text"
                required
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
                className="w-full border-2 border-black focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] px-4 py-3 text-sm font-mono outline-none transition-all duration-200"
                placeholder="Tu nombre"
              />
            </div>
            <div>
              <label className="block text-xs font-mono font-bold uppercase tracking-wider mb-1.5">
                Apellido
              </label>
              <input
                type="text"
                required
                value={apellido}
                onChange={(e) => setApellido(e.target.value)}
                className="w-full border-2 border-black focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] px-4 py-3 text-sm font-mono outline-none transition-all duration-200"
                placeholder="Tu apellido"
              />
            </div>
          </div>

          {/* Teléfono */}
          <div>
            <label className="block text-xs font-mono font-bold uppercase tracking-wider mb-1.5">
              Teléfono <span className="opacity-40">(opcional)</span>
            </label>
            <input
              type="tel"
              value={telefono}
              onChange={(e) => setTelefono(e.target.value)}
              className="w-full border-2 border-black focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] px-4 py-3 text-sm font-mono outline-none transition-all duration-200"
              placeholder="300 123 4567"
            />
          </div>

          {/* Bio */}
          <div>
            <label className="block text-xs font-mono font-bold uppercase tracking-wider mb-1.5">
              Contanos sobre vos <span className="opacity-40">(opcional)</span>
            </label>
            <textarea
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              maxLength={300}
              rows={2}
              className="w-full border-2 border-black focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] px-4 py-3 text-sm font-mono outline-none transition-all duration-200 resize-none"
              placeholder="Artista, gestor cultural, amante del jazz…"
            />
          </div>

          {/* Preferencias culturales */}
          <div>
            <label className="block text-xs font-mono font-bold uppercase tracking-wider mb-3">
              ¿Qué cultura te mueve? <span className="opacity-50">(elegí las que quieras)</span>
            </label>
            <div className="flex flex-wrap gap-2">
              {CATEGORIAS_CULTURALES.map(cat => (
                <button
                  key={cat.value}
                  type="button"
                  onClick={() => togglePref(cat.value)}
                  className={`px-3 py-1.5 text-xs font-mono font-bold uppercase tracking-wider border-2 border-black transition-all duration-200 ${
                    preferencias.includes(cat.value)
                      ? 'bg-black text-white'
                      : 'bg-white text-black hover:bg-black/5'
                  }`}
                >
                  {cat.label}
                </button>
              ))}
            </div>
          </div>

          {/* Zona */}
          <div>
            <label className="block text-xs font-mono font-bold uppercase tracking-wider mb-1.5">
              ¿En qué zona vivís?
            </label>
            <select
              value={zonaId ?? ''}
              onChange={(e) => setZonaId(e.target.value ? Number(e.target.value) : null)}
              className="w-full border-2 border-black focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] px-4 py-3 text-sm font-mono outline-none transition-all duration-200 bg-white"
            >
              <option value="">Seleccionar zona</option>
              {zonas.map(z => (
                <option key={z.id} value={z.id}>{z.nombre} — {z.municipio}</option>
              ))}
            </select>
          </div>

          {/* Barrio */}
          <div>
            <label className="block text-xs font-mono font-bold uppercase tracking-wider mb-1.5">
              Barrio <span className="opacity-40">(opcional)</span>
            </label>
            <input
              type="text"
              value={barrio}
              onChange={(e) => setBarrio(e.target.value)}
              className="w-full border-2 border-black focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] px-4 py-3 text-sm font-mono outline-none transition-all duration-200"
              placeholder="Ej: Laureles, Prado, Buenos Aires…"
            />
          </div>

          {/* Geolocalización */}
          <div>
            <label className="block text-xs font-mono font-bold uppercase tracking-wider mb-1.5">
              Ubicación <span className="opacity-40">(mejora tus recomendaciones)</span>
            </label>
            <button
              type="button"
              onClick={pedirUbicacion}
              disabled={geoLoading}
              className={`w-full flex items-center justify-center gap-2 border-2 border-black px-4 py-3 text-sm font-mono font-bold uppercase tracking-wider transition-all duration-200 ${
                ubicacion ? 'bg-black text-white' : 'hover:bg-black/5'
              }`}
            >
              {geoLoading ? (
                <div className="w-4 h-4 border-2 border-current border-t-transparent animate-spin" />
              ) : ubicacion ? (
                <>◎ Ubicación guardada</>
              ) : (
                <>◎ Compartir mi ubicación</>
              )}
            </button>
          </div>

          {error && (
            <p className="text-sm font-mono border-2 border-black px-4 py-3">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full btn-primary py-3.5 disabled:opacity-50"
          >
            {loading ? '...' : 'Guardar y explorar'}
          </button>
        </form>
      </div>
    </>
  )
}
