import { useState, useEffect } from 'react'

const STORAGE_KEY = 'eterea:onboarding_done'

interface Props {
  onDone: () => void
}

type Phase = 'splash' | 'welcome' | 'notifications' | 'done'

export default function SplashOnboarding({ onDone }: Props) {
  const [phase, setPhase] = useState<Phase>('splash')
  const [logoVisible, setLogoVisible] = useState(false)
  const [textVisible, setTextVisible] = useState(false)

  useEffect(() => {
    // Splash animation sequence
    const t1 = setTimeout(() => setLogoVisible(true), 300)
    const t2 = setTimeout(() => setTextVisible(true), 900)
    const t3 = setTimeout(() => setPhase('welcome'), 2800)
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3) }
  }, [])

  async function handleNotifYes() {
    try {
      const permission = await Notification.requestPermission()
      if (permission !== 'granted') { finish(); return }

      const isCapacitor = typeof (window as unknown as Record<string, unknown>).Capacitor !== 'undefined'

      if (isCapacitor) {
        // Android — FCM
        try {
          const { PushNotifications } = await import('@capacitor/push-notifications')
          await PushNotifications.requestPermissions()
          await PushNotifications.register()
          PushNotifications.addListener('registration', token => {
            fetch('/api/v1/notificaciones/registrar-token', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ token: token.value, platform: 'android' }),
            }).catch(() => {})
          })
        } catch { /* ignore */ }
      } else {
        // Web PWA (iPhone Safari, Chrome desktop, etc.) — Web Push VAPID
        try {
          const sw = await navigator.serviceWorker.ready
          const keyRes = await fetch('/api/v1/notificaciones/vapid-public-key')
          if (keyRes.ok) {
            const { publicKey } = await keyRes.json() as { publicKey: string }
            const sub = await sw.pushManager.subscribe({
              userVisibleOnly: true,
              applicationServerKey: publicKey,
            })
            const subJson = sub.toJSON() as { endpoint: string; keys: Record<string, string> }
            await fetch('/api/v1/notificaciones/registrar-web-push', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ endpoint: subJson.endpoint, keys: subJson.keys }),
            })
          }
        } catch { /* Web push not supported or VAPID not configured */ }
      }
    } catch { /* ignore */ }
    finish()
  }

  function finish() {
    localStorage.setItem(STORAGE_KEY, '1')
    setPhase('done')
    setTimeout(onDone, 400)
  }

  if (phase === 'done') return null

  return (
    <div
      className="fixed inset-0 z-[200] flex flex-col items-center justify-center"
      style={{ backgroundColor: '#0f0a1e' }}
    >
      {/* SPLASH */}
      {phase === 'splash' && (
        <div className="flex flex-col items-center gap-6">
          {/* Logo diamond */}
          <div
            className="transition-all duration-700"
            style={{
              opacity: logoVisible ? 1 : 0,
              transform: logoVisible ? 'scale(1)' : 'scale(0.5)',
            }}
          >
            <div className="relative">
              <div
                className="w-20 h-20 border-2 border-purple-400 rotate-45"
                style={{ borderColor: '#A78BFA' }}
              />
              <span
                className="absolute inset-0 flex items-center justify-center text-3xl font-black"
                style={{ color: '#A78BFA' }}
              >
                ◆
              </span>
            </div>
          </div>

          {/* Text */}
          <div
            className="text-center transition-all duration-700"
            style={{
              opacity: textVisible ? 1 : 0,
              transform: textVisible ? 'translateY(0)' : 'translateY(16px)',
            }}
          >
            <p className="font-mono font-black text-white text-xl uppercase tracking-[0.3em]">
              CULTURA
            </p>
            <p
              className="font-mono font-black text-xl uppercase tracking-[0.3em]"
              style={{ color: '#A78BFA' }}
            >
              ETÉREA
            </p>
            <p className="font-mono text-xs text-white/40 mt-2 uppercase tracking-widest">
              Valle de Aburrá
            </p>
          </div>

          {/* Loading bar */}
          <div
            className="w-24 h-0.5 bg-white/10 overflow-hidden mt-4 transition-all duration-700"
            style={{ opacity: textVisible ? 1 : 0 }}
          >
            <div
              className="h-full bg-purple-400 animate-pulse"
              style={{ backgroundColor: '#A78BFA', width: '60%' }}
            />
          </div>
        </div>
      )}

      {/* WELCOME */}
      {phase === 'welcome' && (
        <div className="flex flex-col items-center gap-8 px-8 max-w-sm w-full animate-fade-in">
          <div className="text-center">
            <span className="text-4xl" style={{ color: '#A78BFA' }}>◆</span>
            <h1 className="font-mono font-black text-white text-2xl uppercase tracking-wider mt-4">
              Bienvenido a<br />
              <span style={{ color: '#A78BFA' }}>Cultura ETÉREA</span>
            </h1>
            <p className="font-mono text-white/60 text-sm mt-4 leading-relaxed">
              Tu radar cultural del Valle de Aburrá — teatro, música, danza, arte y más.
            </p>
          </div>

          <div className="space-y-3 w-full">
            <div className="flex items-center gap-3 border border-white/10 rounded p-3">
              <span className="text-lg">🎭</span>
              <p className="font-mono text-white/70 text-xs">Eventos esta semana cerca de ti</p>
            </div>
            <div className="flex items-center gap-3 border border-white/10 rounded p-3">
              <span className="text-lg">📍</span>
              <p className="font-mono text-white/70 text-xs">Filtra por barrio, categoría y precio</p>
            </div>
            <div className="flex items-center gap-3 border border-white/10 rounded p-3">
              <span className="text-lg">🔍</span>
              <p className="font-mono text-white/70 text-xs">Descubre colectivos y espacios culturales</p>
            </div>
          </div>

          <button
            onClick={() => setPhase('notifications')}
            className="w-full py-4 font-mono font-black text-sm uppercase tracking-widest text-black transition-all"
            style={{ backgroundColor: '#A78BFA' }}
          >
            Explorar →
          </button>
        </div>
      )}

      {/* NOTIFICATION PERMISSION */}
      {phase === 'notifications' && (
        <div className="flex flex-col items-center gap-8 px-8 max-w-sm w-full">
          <div className="text-center">
            <div className="text-5xl mb-4">🔔</div>
            <h2 className="font-mono font-black text-white text-xl uppercase tracking-wider">
              ¿Te avisamos?
            </h2>
            <p className="font-mono text-white/60 text-sm mt-4 leading-relaxed">
              Activa las notificaciones y te contamos cuando hay eventos nuevos hoy en Medellín y cuando se acerca algo que no te puedes perder.
            </p>
          </div>

          <div className="space-y-3 w-full">
            <div className="flex items-center gap-3 p-3 border border-white/10 rounded">
              <span>🎵</span>
              <p className="font-mono text-white/60 text-xs">"Esta noche: Jazz en Laureles — entrada libre"</p>
            </div>
            <div className="flex items-center gap-3 p-3 border border-white/10 rounded">
              <span>🎪</span>
              <p className="font-mono text-white/60 text-xs">"5 eventos nuevos agregados hoy en Medellín"</p>
            </div>
            <div className="flex items-center gap-3 p-3 border border-white/10 rounded">
              <span>📅</span>
              <p className="font-mono text-white/60 text-xs">"Tu agenda cultural de esta semana"</p>
            </div>
          </div>

          <div className="space-y-3 w-full">
            <button
              onClick={handleNotifYes}
              className="w-full py-4 font-mono font-black text-sm uppercase tracking-widest text-black transition-all"
              style={{ backgroundColor: '#A78BFA' }}
            >
              Sí, activar notificaciones
            </button>
            <button
              onClick={finish}
              className="w-full py-3 font-mono text-xs uppercase tracking-widest text-white/40 hover:text-white/70 transition-colors"
            >
              Ahora no
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export function shouldShowOnboarding(): boolean {
  return !localStorage.getItem(STORAGE_KEY)
}
