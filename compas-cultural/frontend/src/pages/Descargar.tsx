import { useState, useEffect } from 'react'
import { Helmet } from 'react-helmet-async'
import { Link } from 'react-router-dom'

export default function Descargar() {
  const [deferredPrompt, setDeferredPrompt] = useState<Event | null>(null)
  const [installed, setInstalled] = useState(false)
  const [isIOS, setIsIOS] = useState(false)
  const [isAndroid, setIsAndroid] = useState(false)

  useEffect(() => {
    const ua = navigator.userAgent
    setIsIOS(/iPad|iPhone|iPod/.test(ua))
    setIsAndroid(/Android/.test(ua))

    const handler = (e: Event) => { e.preventDefault(); setDeferredPrompt(e) }
    window.addEventListener('beforeinstallprompt', handler)
    window.addEventListener('appinstalled', () => setInstalled(true))
    return () => window.removeEventListener('beforeinstallprompt', handler)
  }, [])

  async function handleInstall() {
    if (!deferredPrompt) return
    const prompt = deferredPrompt as BeforeInstallPromptEvent
    prompt.prompt()
    const { outcome } = await prompt.userChoice
    if (outcome === 'accepted') setInstalled(true)
    setDeferredPrompt(null)
  }

  return (
    <>
      <Helmet>
        <title>Descargar — Cultura ETÉREA</title>
      </Helmet>
      <div className="max-w-2xl mx-auto px-4 py-12">
        <Link to="/" className="font-mono text-xs uppercase tracking-wider hover:underline mb-8 inline-block">← Volver</Link>

        <div className="text-center mb-10">
          <span className="text-5xl font-black" style={{ color: '#A78BFA' }}>◆</span>
          <h1 className="text-3xl font-mono font-black uppercase mt-3 mb-2">Cultura ETÉREA</h1>
          <p className="font-mono text-sm text-neutral-500">Instala la app en tu dispositivo — gratis, sin registro</p>
        </div>

        {/* Android — Play Store */}
        <div className="border-2 border-black p-6 mb-4">
          <div className="flex items-center gap-3 mb-4">
            <span className="text-2xl">🤖</span>
            <div>
              <p className="font-mono font-bold text-sm uppercase tracking-wider">Android</p>
              <p className="font-mono text-xs text-neutral-500">Google Play Store</p>
            </div>
          </div>
          {isAndroid && deferredPrompt && !installed ? (
            <button onClick={handleInstall}
              className="w-full py-3 bg-black text-white font-mono font-bold uppercase tracking-widest text-sm hover:bg-yellow-300 hover:text-black transition-colors">
              ✨ Instalar ahora
            </button>
          ) : installed ? (
            <p className="font-mono text-sm text-green-700 font-bold">✓ App instalada correctamente</p>
          ) : (
            <a href="https://play.google.com/store/apps/details?id=co.eterea.cultura"
              target="_blank" rel="noopener noreferrer"
              className="block w-full py-3 bg-black text-white font-mono font-bold uppercase tracking-widest text-sm text-center hover:bg-yellow-300 hover:text-black transition-colors">
              Ver en Google Play →
            </a>
          )}
        </div>

        {/* iPhone — PWA */}
        <div className="border-2 border-black p-6 mb-4">
          <div className="flex items-center gap-3 mb-4">
            <span className="text-2xl">🍎</span>
            <div>
              <p className="font-mono font-bold text-sm uppercase tracking-wider">iPhone / iPad</p>
              <p className="font-mono text-xs text-neutral-500">Instalar desde Safari — gratis</p>
            </div>
          </div>
          {isIOS ? (
            <div className="space-y-3">
              <p className="font-mono text-xs text-neutral-600 bg-neutral-50 p-3 border border-black/10">
                Estás en iPhone. Sigue estos pasos:
              </p>
              <div className="space-y-2">
                {[
                  { n: 1, text: 'Abre esta página en Safari (no en Chrome)' },
                  { n: 2, text: 'Toca el ícono ⬆️ de compartir abajo' },
                  { n: 3, text: 'Selecciona "Añadir a pantalla de inicio"' },
                  { n: 4, text: 'Toca "Añadir" — ¡listo!' },
                ].map(s => (
                  <div key={s.n} className="flex items-start gap-3">
                    <span className="w-6 h-6 bg-black text-white text-xs font-mono font-bold flex items-center justify-center shrink-0">{s.n}</span>
                    <p className="font-mono text-xs text-neutral-600 pt-0.5">{s.text}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              {[
                { n: 1, text: 'Abre culturaetereamed.com en Safari en tu iPhone' },
                { n: 2, text: 'Toca el ícono ⬆️ de compartir abajo' },
                { n: 3, text: 'Selecciona "Añadir a pantalla de inicio"' },
                { n: 4, text: 'Toca "Añadir" — aparece el ícono como app' },
              ].map(s => (
                <div key={s.n} className="flex items-start gap-3">
                  <span className="w-6 h-6 bg-black text-white text-xs font-mono font-bold flex items-center justify-center shrink-0">{s.n}</span>
                  <p className="font-mono text-xs text-neutral-600 pt-0.5">{s.text}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Desktop / Chrome */}
        <div className="border-2 border-black p-6 mb-8">
          <div className="flex items-center gap-3 mb-4">
            <span className="text-2xl">💻</span>
            <div>
              <p className="font-mono font-bold text-sm uppercase tracking-wider">PC / Mac / Chromebook</p>
              <p className="font-mono text-xs text-neutral-500">Chrome o Edge — instalar como app</p>
            </div>
          </div>
          {deferredPrompt && !installed ? (
            <button onClick={handleInstall}
              className="w-full py-3 bg-black text-white font-mono font-bold uppercase tracking-widest text-sm hover:bg-yellow-300 hover:text-black transition-colors">
              ✨ Instalar en este dispositivo
            </button>
          ) : (
            <p className="font-mono text-xs text-neutral-500">
              En Chrome: clic en el ícono ⊕ en la barra de dirección → "Instalar Cultura ETÉREA"
            </p>
          )}
        </div>

        <p className="font-mono text-xs text-neutral-400 text-center">
          La app siempre está actualizada automáticamente.<br/>
          No ocupa espacio — carga directo desde internet.
        </p>
      </div>
    </>
  )
}

interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}
