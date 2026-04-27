import { Helmet } from 'react-helmet-async'
import { useState, useEffect, useRef, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../lib/AuthContext'
import {
  registrarPorURL,
  consultarEstadoRegistro,
  getEspacio,
  type RegistroURLResponse,
  type RegistroEstadoResponse,
} from '../lib/api'

type Fase = 'formulario' | 'procesando' | 'resultado'

export default function Registrar() {
  const { user } = useAuth()
  const [url, setUrl] = useState('')
  const [fase, setFase] = useState<Fase>('formulario')
  const [solicitud, setSolicitud] = useState<RegistroURLResponse | null>(null)
  const [estado, setEstado] = useState<RegistroEstadoResponse | null>(null)
  const [perfilRef, setPerfilRef] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [aceptaDatos, setAceptaDatos] = useState(false)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const limpiarPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }, [])

  useEffect(() => {
    return () => limpiarPolling()
  }, [limpiarPolling])

  const enviarURL = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url.trim()) return

    setError(null)
    setFase('procesando')

    try {
      const resp = await registrarPorURL(url.trim(), aceptaDatos)
      setSolicitud(resp)
      iniciarPolling(resp.id)
    } catch {
      setError('No fue posible enviar la URL. Revisa la dirección e intenta nuevamente.')
      setFase('formulario')
    }
  }

  const iniciarPolling = (id: number) => {
    limpiarPolling()

    pollingRef.current = setInterval(async () => {
      try {
        const resp = await consultarEstadoRegistro(id)
        setEstado(resp)

        if (resp.estado === 'completado' || resp.estado === 'fallido' || resp.estado === 'error' || resp.estado === 'rechazado') {
          limpiarPolling()
          setFase('resultado')
        }
      } catch {
        // Seguir intentando
      }
    }, 2000)
  }

  const reiniciar = () => {
    limpiarPolling()
    setUrl('')
    setFase('formulario')
    setSolicitud(null)
    setEstado(null)
    setPerfilRef(null)
    setError(null)
  }

  useEffect(() => {
    if (!estado || estado.estado !== 'completado') return

    const datos = (estado.datos_extraidos ?? {}) as Record<string, unknown>
    const nestedEspacio = (datos.espacio as Record<string, unknown> | undefined) ?? undefined

    const readNonEmpty = (...vals: unknown[]): string | null => {
      for (const v of vals) {
        if (typeof v === 'string') {
          const s = v.trim()
          if (s && s !== 'null' && s !== 'undefined') return s
        }
      }
      return null
    }

    const optimisticRef = readNonEmpty(
      datos.slug,
      nestedEspacio?.slug,
      estado.espacio_id,
      datos.id,
      nestedEspacio?.id,
    )

    if (optimisticRef) setPerfilRef(optimisticRef)

    if (!estado.espacio_id) return

    let cancelled = false
    const resolveCanonical = async () => {
      try {
        const espacio = await getEspacio(estado.espacio_id as string)
        if (cancelled) return
        setPerfilRef((espacio.slug && espacio.slug.trim()) || espacio.id)
      } catch {
        // Keep optimisticRef fallback already set.
      }
    }

    void resolveCanonical()

    return () => {
      cancelled = true
    }
  }, [estado])

  return (
    <>
      <Helmet>
        <title>Registrar Espacio - Cultura ETÉREA</title>
      </Helmet>

      <div className="max-w-2xl mx-auto px-4 py-12">
        <h1 className="text-4xl font-mono font-bold mb-4">REGISTRA TU ESPACIO</h1>
        <p className="font-mono mb-6">
          Pega el link de tu centro cultural, proyecto, programa o Instagram.
          Nuestro sistema extraerá la información automáticamente y tu espacio quedará conectado
          al scraping activo — actualizaremos tus eventos en tiempo real.
        </p>
        <div className="border-2 border-black p-4 mb-8">
          <p className="font-mono text-xs uppercase tracking-wider">
            Política de datos: este sistema está orientado a cultura. No se deben registrar cuentas personales.
            <Link to="/proteccion-datos" className="ml-2 underline font-bold">Ley de protección de datos</Link>
          </p>
        </div>

        {/* Prompt para crear cuenta */}
        {!user && (
          <div className="border-2 border-black p-5 mb-8 bg-white">
            <div className="flex items-center gap-3 mb-2">
              <span className="w-3 h-3 bg-black" />
              <span className="text-xs font-mono font-bold uppercase tracking-wider">Creá tu cuenta primero</span>
            </div>
            <p className="text-sm font-mono mb-4 opacity-70">
              Para gestionar tu espacio, recibir notificaciones y ver estadísticas, necesitás una cuenta.
            </p>
            <Link
              to="/login"
              className="inline-flex items-center gap-2 bg-black text-white px-6 py-3 font-mono text-xs font-bold uppercase tracking-wider hover:bg-white hover:text-black border-2 border-black transition-all duration-300"
            >
              Crear cuenta o iniciar sesión
              <span>→</span>
            </Link>
          </div>
        )}

        {/* ---------- FORMULARIO ---------- */}
        {fase === 'formulario' && (
          <div>
            <form onSubmit={enviarURL} className="space-y-6">
              <div>
                <label htmlFor="url-input" className="block font-mono text-sm font-bold mb-2">
                  URL O PERFIL
                </label>
                <input
                  id="url-input"
                  type="text"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://instagram.com/micentrocultural  o  www.miproyecto.com"
                  className="w-full px-4 py-3 border-2 border-black focus:outline-none focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] font-mono text-sm transition-all"
                  autoFocus
                />
                <p className="text-xs font-mono mt-2">
                  Acepta links de Instagram, sitios web, Facebook y Google Maps
                </p>
              </div>

              {error && <p className="text-red-600 text-sm">{error}</p>}

              <label className="flex items-start gap-2 border-2 border-black p-3 text-xs font-mono">
                <input
                  type="checkbox"
                  checked={aceptaDatos}
                  onChange={(e) => setAceptaDatos(e.target.checked)}
                  className="mt-0.5"
                />
                <span>
                  Confirmo que la URL corresponde a un espacio/colectivo cultural público y acepto la
                  <Link to="/proteccion-datos" className="underline font-bold ml-1">política de protección de datos</Link>.
                </span>
              </label>

              <button
                type="submit"
                disabled={!url.trim() || !user || !aceptaDatos}
                className="w-full bg-black text-white py-3 font-mono text-sm uppercase tracking-wider hover:bg-white hover:text-black border-2 border-black disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-300"
              >
                {user ? 'Registrar espacio' : 'Inicia sesión para registrar'}
              </button>
            </form>

            <div className="mt-12 border-t-2 border-black pt-8">
              <h3 className="font-mono font-bold text-sm mb-4">¿QUÉ TIPO DE LINKS ACEPTA?</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {[
                  { tipo: 'Instagram', ejemplo: 'instagram.com/teatromatacandelas', icono: '📷' },
                  { tipo: 'Sitio web', ejemplo: 'www.casatrespatios.org', icono: '🌐' },
                  { tipo: 'Google Maps', ejemplo: 'maps.google.com/...', icono: '📍' },
                  { tipo: 'Facebook', ejemplo: 'facebook.com/milocalcultural', icono: '👤' },
                ].map((item) => (
                  <div key={item.tipo} className="border-2 border-black p-3">
                    <span className="text-lg mr-2">{item.icono}</span>
                    <span className="font-mono text-xs font-bold uppercase">{item.tipo}</span>
                    <p className="text-xs font-mono mt-1">{item.ejemplo}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ---------- PROCESANDO ---------- */}
        {fase === 'procesando' && (
          <div className="text-center py-16">
            <ScrapingAnimation />
            <p className="font-mono text-sm mt-6">
              {estado?.mensaje ?? solicitud?.mensaje ?? 'Iniciando extracción…'}
            </p>
            <p className="text-xs font-mono mt-2">
              Analizando: <span className="font-mono">{solicitud?.url ?? url}</span>
            </p>
            <p className="text-xs font-mono mt-4 opacity-60">
              Tipo detectado: <span className="font-mono uppercase">{solicitud?.tipo_url ?? '…'}</span>
            </p>
          </div>
        )}

        {/* ---------- RESULTADO ---------- */}
        {fase === 'resultado' && estado && (
          <div className="space-y-8">
            {estado.estado === 'completado' ? (
              <ResultadoExitoso estado={estado} />
            ) : (
              <ResultadoError estado={estado} />
            )}

            <div className="flex gap-4">
              <button
                onClick={reiniciar}
                className="flex-1 border-2 border-black py-3 font-mono text-sm uppercase tracking-wider hover:bg-black hover:text-white transition-all duration-300"
              >
                Registrar otro
              </button>
              {estado.espacio_id && estado.estado === 'completado' && perfilRef && (
                <Link
                  to={`/espacio/${encodeURIComponent(perfilRef)}`}
                  className="flex-1 bg-black text-white py-3 font-mono text-sm uppercase tracking-wider hover:bg-white hover:text-black border-2 border-black transition-all duration-300 text-center"
                >
                  Ver perfil
                </Link>
              )}
              {estado.estado === 'completado' && (
                <Link
                  to="/colectivos"
                  className="flex-1 border-2 border-black py-3 font-mono text-sm uppercase tracking-wider hover:bg-black hover:text-white transition-all duration-300 text-center"
                >
                  Ver colectivos
                </Link>
              )}
            </div>
          </div>
        )}
      </div>
    </>
  )
}


/* ------------------------------------------------------------------ */
/* Componentes internos                                                */
/* ------------------------------------------------------------------ */

function ScrapingAnimation() {
  const [dots, setDots] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => setDots((d) => (d + 1) % 4), 400)
    return () => clearInterval(timer)
  }, [])

  const pasos = [
    'Conectando con la URL',
    'Leyendo contenido de la página',
    'Extrayendo datos culturales',
    'Identificando categoría',
    'Creando perfil',
  ]

  return (
    <div className="space-y-4">
      <div className="flex justify-center">
        <div className="relative w-16 h-16">
          <div className="absolute inset-0 border-2 border-black" />
          <div className="absolute inset-0 border-2 border-black border-t-transparent animate-spin" />
        </div>
      </div>

      <div className="space-y-2 text-left max-w-xs mx-auto">
        {pasos.map((paso, i) => (
          <div key={paso} className="flex items-center gap-2 text-xs">
            <span className={i <= dots ? 'text-black' : 'opacity-30'}>
              {i < dots ? '✓' : i === dots ? '→' : '○'}
            </span>
            <span className={i <= dots ? 'text-black' : 'opacity-30'}>{paso}</span>
          </div>
        ))}
      </div>
    </div>
  )
}


function ResultadoExitoso({ estado }: Readonly<{ estado: RegistroEstadoResponse }>) {
  const datos = estado.datos_extraidos as Record<string, string | number | null> | null
  const datosObj = (estado.datos_extraidos as Record<string, unknown> | null) ?? null
  const espacio = (datosObj?.espacio as Record<string, unknown> | undefined) ?? undefined

  const readText = (...values: unknown[]) => {
    for (const value of values) {
      if (typeof value === 'string' && value.trim()) return value.trim()
      if (typeof value === 'number') return String(value)
    }
    return null
  }

  const nombre = readText(datosObj?.nombre, espacio?.nombre)
  const categoria = readText(datosObj?.categoria_sugerida, datosObj?.categoria_principal, espacio?.categoria_principal)
  const instagramRaw = readText(datosObj?.instagram_handle, espacio?.instagram_handle)
  const instagram = instagramRaw ? `@${instagramRaw.replace(/^@+/, '')}` : null
  const web = readText(datosObj?.sitio_web, espacio?.sitio_web)
  const descripcion = readText(datosObj?.descripcion_corta, espacio?.descripcion_corta)
  const fuente = readText(datosObj?.fuente)

  return (
    <div className="space-y-6">
      <div className="border border-black p-6">
        <div className="flex items-center gap-3 mb-4">
          <span className="text-2xl">✓</span>
          <h2 className="text-xl font-mono font-bold">REGISTRADO</h2>
        </div>

        <p className="text-sm font-mono mb-6">{estado.mensaje}</p>

        {(datos || datosObj) && (
          <div className="space-y-3 border-2 border-black p-4">
            <DatoExtraido label="Nombre" valor={nombre} />
            <DatoExtraido label="Categoría" valor={categoria} />
            <DatoExtraido label="Instagram" valor={instagram} />
            <DatoExtraido label="Web" valor={web} />
            <DatoExtraido label="Descripción" valor={descripcion} />
            <DatoExtraido label="Fuente" valor={fuente} />
          </div>
        )}
      </div>

      {/* Scraping activo notice */}
      <div className="border-2 border-black p-5 bg-black text-white">
        <div className="flex items-center gap-2 mb-2">
          <span className="w-2 h-2 bg-white animate-pulse" />
          <span className="text-[11px] font-mono font-bold uppercase tracking-wider">Scraping activo conectado</span>
        </div>
        <p className="text-xs font-mono opacity-80">
          Tu espacio queda conectado a nuestro sistema de escucha automática.
          Cada 6 horas revisamos tu web e Instagram para publicar tus eventos en tiempo real.
        </p>
      </div>
    </div>
  )
}


function ResultadoError({ estado }: Readonly<{ estado: RegistroEstadoResponse }>) {
  return (
    <div className="border-2 border-black p-6">
      <div className="flex items-center gap-3 mb-4">
        <span className="text-2xl">✗</span>
        <h2 className="text-xl font-mono font-bold">ERROR</h2>
      </div>
      <p className="text-sm font-mono">{estado.mensaje ?? 'No fue posible procesar la URL.'}</p>
    </div>
  )
}


function DatoExtraido({ label, valor }: Readonly<{ label: string; valor: string | number | null | undefined }>) {
  if (!valor) return null

  return (
    <div className="flex gap-2 text-sm">
      <span className="font-mono font-bold w-24 shrink-0 uppercase tracking-wider">{label}</span>
      <span>{String(valor)}</span>
    </div>
  )
}
