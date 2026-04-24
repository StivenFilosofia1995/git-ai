import { useState, useEffect } from 'react'
import { Helmet } from 'react-helmet-async'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import { useAuth } from '../lib/AuthContext'
import { crearPerfil, getZonas, CATEGORIAS_CULTURALES, type Zona } from '../lib/api'

type Mode = 'login' | 'register'
type RegisterStep = 'credentials' | 'profile'

export default function Login() {
  const { signIn, signUp, signInWithGoogle } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const redirectTo = (location.state as { from?: string })?.from ?? '/'
  const [mode, setMode] = useState<Mode>('login')
  const [step, setStep] = useState<RegisterStep>('credentials')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [nombre, setNombre] = useState('')
  const [apellido, setApellido] = useState('')
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
  const [confirmSent, setConfirmSent] = useState(false)
  const [aceptaPolitica, setAceptaPolitica] = useState(false)
  const [aceptaTratamiento, setAceptaTratamiento] = useState(false)

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
    setError(null)
    setLoading(true)

    if (mode === 'register') {
      if (step === 'credentials') {
        if (!nombre.trim() || !apellido.trim()) {
          setError('Nombre y apellido son obligatorios')
          setLoading(false)
          return
        }
        if (!aceptaPolitica || !aceptaTratamiento) {
          setError('Debes aceptar la política de datos y el consentimiento para registrarte')
          setLoading(false)
          return
        }
        setStep('profile')
        setLoading(false)
        return
      }

      // step === 'profile' → crear cuenta + perfil
      const { error: err } = await signUp(email, password, {
        acepta_politica_datos: true,
        acepta_tratamiento_datos: true,
        consentimiento_at: new Date().toISOString(),
      })
      if (err) {
        setError(err)
        setLoading(false)
        return
      }

      // Save profile data locally — will be created after email confirmation
      try {
        const profileData = {
          nombre: nombre.trim(),
          apellido: apellido.trim(),
          email,
          preferencias,
          zona_id: zonaId ?? undefined,
          telefono: telefono.trim() || undefined,
          bio: bio.trim() || undefined,
          ubicacion_barrio: barrio.trim() || undefined,
          ubicacion_lat: ubicacion?.lat,
          ubicacion_lng: ubicacion?.lng,
        }
        localStorage.setItem('eterea_pending_profile', JSON.stringify(profileData))

        // Try creating profile immediately (works if email confirmation is disabled)
        const { data } = await import('../lib/supabase').then(m => m.supabase.auth.getUser())
        if (data?.user) {
          await crearPerfil(profileData, data.user.id)
          localStorage.removeItem('eterea_pending_profile')
        }
      } catch {
        // Profile will be created on first sign-in via AuthContext
      }

      // Send welcome email immediately after signup
      try {
        const apiBase = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'
        fetch(`${apiBase}/auth/welcome-email`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, nombre: nombre.trim() }),
        }).catch(() => {})
      } catch { /* best-effort */ }

      setConfirmSent(true)
    } else {
      const { error: err } = await signIn(email, password)
      if (err) {
        setError(err)
      } else {
        navigate(redirectTo)
      }
    }

    setLoading(false)
  }

  const handleGoogle = async () => {
    setError(null)
    const { error: err } = await signInWithGoogle()
    if (err) setError(err)
  }

  if (confirmSent) {
    return (
      <div className="max-w-md mx-auto px-6 py-20 text-center">
        <div className="bg-white border-2 border-black p-10">
          <span className="text-4xl mb-4 block">✉️</span>
          <h2 className="text-xl font-heading font-black mb-2 uppercase">Revisá tu email</h2>
          <p className="text-sm font-mono mb-6">
            Enviamos un enlace de confirmación a <strong>{email}</strong>.
            Hacé clic en el enlace para activar tu cuenta.
          </p>
          <button
            onClick={() => { setConfirmSent(false); setMode('login') }}
            className="text-sm font-mono font-bold uppercase tracking-wider hover:underline transition-colors"
          >
            Volver a iniciar sesión
          </button>
        </div>
      </div>
    )
  }

  return (
    <>
      <Helmet>
        <title>{mode === 'login' ? 'Iniciar Sesión' : 'Crear Cuenta'} — Cultura ETÉREA</title>
      </Helmet>

      <div className="max-w-md mx-auto px-6 py-16">
        <div className="text-center mb-10">
          <div className="w-12 h-12 bg-black flex items-center justify-center mx-auto mb-4">
            <span className="text-white font-heading font-bold text-lg">E</span>
          </div>
          <h1 className="text-2xl font-heading font-black tracking-tight mb-1 uppercase">
            {mode === 'login' ? 'Bienvenido de vuelta' : 'Crear cuenta'}
          </h1>
          <p className="text-sm font-mono uppercase tracking-wider">Cultura ETÉREA · Medellín</p>
        </div>

        {/* Google OAuth */}
        <button
          onClick={handleGoogle}
          className="w-full flex items-center justify-center gap-3 border-2 border-black hover:bg-black hover:text-white
                     px-4 py-3.5 text-sm font-mono font-bold uppercase tracking-wider transition-all duration-300 mb-6"
        >
          <svg width="18" height="18" viewBox="0 0 48 48">
            <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
            <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
            <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
            <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
          </svg>
          Continuar con Google
        </button>

        <div className="flex items-center gap-3 mb-6">
          <div className="flex-1 h-[2px] bg-black" />
          <span className="text-[11px] font-mono font-bold uppercase tracking-wider">o con email</span>
          <div className="flex-1 h-[2px] bg-black" />
        </div>

        {/* Email form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Step 1: Credentials + nombre/apellido (register) */}
          {(mode === 'login' || step === 'credentials') && (
            <>
              {mode === 'register' && (
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
                      className="w-full border-2 border-black focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] px-4 py-3 text-sm font-mono
                                 outline-none transition-all duration-200"
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
                      className="w-full border-2 border-black focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] px-4 py-3 text-sm font-mono
                                 outline-none transition-all duration-200"
                      placeholder="Tu apellido"
                    />
                  </div>
                </div>
              )}

              <div>
                <label className="block text-xs font-mono font-bold uppercase tracking-wider mb-1.5">
                  Email
                </label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full border-2 border-black focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] px-4 py-3 text-sm font-mono
                             outline-none transition-all duration-200"
                  placeholder="tu@email.com"
                />
              </div>

              <div>
                <label className="block text-xs font-mono font-bold uppercase tracking-wider mb-1.5">
                  Contraseña
                </label>
                <input
                  type="password"
                  required
                  minLength={6}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full border-2 border-black focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] px-4 py-3 text-sm font-mono
                             outline-none transition-all duration-200"
                  placeholder="Contraseña"
                />
              </div>

              {mode === 'register' && (
                <div className="border-2 border-black p-3 space-y-2">
                  <label className="flex items-start gap-2 text-xs font-mono">
                    <input
                      type="checkbox"
                      checked={aceptaPolitica}
                      onChange={(e) => setAceptaPolitica(e.target.checked)}
                      className="mt-0.5"
                    />
                    <span>
                      Acepto la <Link to="/proteccion-datos" className="underline font-bold">Ley de protección de datos</Link> y la política de privacidad cultural.
                    </span>
                  </label>
                  <label className="flex items-start gap-2 text-xs font-mono">
                    <input
                      type="checkbox"
                      checked={aceptaTratamiento}
                      onChange={(e) => setAceptaTratamiento(e.target.checked)}
                      className="mt-0.5"
                    />
                    <span>
                      Autorizo el tratamiento de mis datos para fines de operación de la plataforma cultural.
                    </span>
                  </label>
                </div>
              )}
            </>
          )}

          {/* Step 2: Preferencias culturales + zona + datos extra (register only) */}
          {mode === 'register' && step === 'profile' && (
            <>
              {/* Teléfono */}
              <div>
                <label className="block text-xs font-mono font-bold uppercase tracking-wider mb-1.5">
                  Teléfono <span className="opacity-40">(opcional)</span>
                </label>
                <input
                  type="tel"
                  value={telefono}
                  onChange={(e) => setTelefono(e.target.value)}
                  className="w-full border-2 border-black focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] px-4 py-3 text-sm font-mono
                             outline-none transition-all duration-200"
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
                  className="w-full border-2 border-black focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] px-4 py-3 text-sm font-mono
                             outline-none transition-all duration-200 resize-none"
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
                  className="w-full border-2 border-black focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] px-4 py-3 text-sm font-mono
                             outline-none transition-all duration-200 bg-white"
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
                  className="w-full border-2 border-black focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] px-4 py-3 text-sm font-mono
                             outline-none transition-all duration-200"
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

              <button
                type="button"
                onClick={() => setStep('credentials')}
                className="text-xs font-mono font-bold uppercase tracking-wider hover:underline"
              >
                ← Volver
              </button>
            </>
          )}

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
            {loading ? '...' : mode === 'login' ? 'Entrar' : step === 'credentials' ? 'Siguiente →' : 'Crear cuenta'}
          </button>
        </form>

        <div className="text-center mt-6">
          <button
            onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(null); setStep('credentials') }}
            className="text-sm font-mono font-bold uppercase tracking-wider hover:underline transition-colors"
          >
            {mode === 'login'
              ? '¿No tenés cuenta? Crear cuenta'
              : '¿Ya tenés cuenta? Iniciar sesión'}
          </button>
        </div>
      </div>
    </>
  )
}
