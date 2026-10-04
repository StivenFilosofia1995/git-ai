import { Link } from 'react-router-dom'
import Navigation from './Navigation'
import MobileNav from './MobileNav'
import { useAuth } from '../../lib/AuthContext'
import { useState, useRef, useEffect } from 'react'

export default function Header() {
  const { user, signOut, loading } = useAuth()

  return (
    <>
      <header className="sticky top-0 z-40 bg-white border-b-2 border-black">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between gap-3">
          <Link to="/" className="flex items-center gap-3 group">
            <div className="w-9 h-9 bg-black flex items-center justify-center group-hover:bg-white group-hover:outline group-hover:outline-2 group-hover:outline-black transition-all duration-300">
              <span className="text-white font-heading font-black text-base group-hover:text-black transition-colors duration-300">E</span>
            </div>
            <div>
              <span className="block text-sm font-heading font-black tracking-tight leading-none uppercase">CULTURA ETÉREA</span>
              <p className="text-[10px] text-black/60 tracking-[0.08em] sm:tracking-[0.2em] xl:tracking-[0.12em] uppercase leading-none mt-0.5 font-mono whitespace-nowrap">
                Agenda del Valle de Aburrá<span className="hidden xl:inline"> · agéntica y autónoma con IA</span>
              </p>
              <p className="xl:hidden text-[9px] text-black/50 tracking-[0.08em] sm:tracking-[0.16em] uppercase leading-none mt-0.5 font-mono whitespace-nowrap">
                Agéntica y autónoma con IA
              </p>
            </div>
          </Link>
          <div className="flex items-center gap-2 lg:gap-4">
            <Navigation />

            <RegisterDropdown />

            <Link
              to="/guardados"
              className="hidden md:flex items-center gap-1 px-2 py-1.5 text-sm font-bold hover:bg-black hover:text-white transition-colors border border-transparent hover:border-black"
              title="Eventos guardados"
            >
              ♡ <span className="hidden lg:inline">Guardados</span>
            </Link>

            {!loading && (
              user ? (
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 bg-black text-white flex items-center justify-center text-xs font-heading font-black uppercase">
                    {user.email?.charAt(0) ?? '?'}
                  </div>
                  <button
                    onClick={() => signOut()}
                    className="text-xs text-black hover:underline underline-offset-4 transition-all font-mono uppercase tracking-wider"
                  >
                    Salir
                  </button>
                </div>
              ) : (
                <Link
                  to="/login"
                  className="btn-primary text-[11px] !py-2 !px-5"
                >
                  Entrar
                </Link>
              )
            )}
          </div>
        </div>
      </header>
      <MobileNav />
    </>
  )
}

function RegisterDropdown() {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div ref={ref} className="relative hidden md:block">
      <button
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-1.5 px-3 py-1.5 border-2 border-black text-[10px] font-mono font-bold uppercase tracking-wider hover:bg-black hover:text-white transition-all duration-200"
      >
        + Publicar
        <span className={`transition-transform duration-200 ${open ? 'rotate-180' : ''}`}>▾</span>
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 w-52 bg-white border-2 border-black z-50 shadow-lg">
          <Link
            to="/publicar"
            onClick={() => setOpen(false)}
            className="block px-4 py-3 text-xs font-mono font-bold uppercase tracking-wider hover:bg-black hover:text-white transition-all border-b border-black"
          >
            📤 Publicar evento
          </Link>
          <Link
            to="/registrar"
            onClick={() => setOpen(false)}
            className="block px-4 py-3 text-xs font-mono font-bold uppercase tracking-wider hover:bg-black hover:text-white transition-all border-b border-black"
          >
            🏛 Registrar espacio
          </Link>
          <Link
            to="/registrar"
            onClick={() => setOpen(false)}
            className="block px-4 py-3 text-xs font-mono font-bold uppercase tracking-wider hover:bg-black hover:text-white transition-all"
          >
            🎨 Registrar colectivo
          </Link>
        </div>
      )}
    </div>
  )
}