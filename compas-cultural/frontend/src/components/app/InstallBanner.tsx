import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

const DISMISSED_KEY = 'eterea:install_banner_dismissed'

export default function InstallBanner() {
  const [show, setShow] = useState(false)
  const [isStandalone, setIsStandalone] = useState(false)

  useEffect(() => {
    // Don't show if already installed or dismissed
    const standalone = window.matchMedia('(display-mode: standalone)').matches
      || (navigator as Navigator & { standalone?: boolean }).standalone === true
    setIsStandalone(standalone)

    if (standalone) return
    if (localStorage.getItem(DISMISSED_KEY)) return
    if (!/Mobi|Android|iPhone|iPad/i.test(navigator.userAgent)) return

    // Show after 12 seconds
    const t = setTimeout(() => setShow(true), 12000)
    return () => clearTimeout(t)
  }, [])

  function dismiss() {
    localStorage.setItem(DISMISSED_KEY, '1')
    setShow(false)
  }

  if (!show || isStandalone) return null

  return (
    <div className="fixed bottom-16 left-3 right-3 z-[90] md:hidden">
      <div className="bg-black text-white border-2 border-black shadow-[4px_4px_0px_0px_rgba(167,139,250,1)] flex items-center gap-3 p-3">
        <span className="text-2xl shrink-0">◆</span>
        <div className="flex-1 min-w-0">
          <p className="font-mono font-bold text-xs uppercase tracking-wider">Instala la app</p>
          <p className="font-mono text-[10px] text-white/60">Accede más rápido sin abrir el navegador</p>
        </div>
        <Link to="/descargar" onClick={dismiss}
          className="shrink-0 px-3 py-1.5 font-mono font-bold text-[10px] uppercase tracking-wider"
          style={{ backgroundColor: '#A78BFA', color: '#000' }}>
          Instalar
        </Link>
        <button onClick={dismiss} className="shrink-0 text-white/40 hover:text-white text-lg font-black ml-1">✕</button>
      </div>
    </div>
  )
}
