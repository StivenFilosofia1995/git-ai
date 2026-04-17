import { Link } from 'react-router-dom'
import Navigation from './Navigation'
import MobileNav from './MobileNav'
import { useAuth } from '../../lib/AuthContext'

export default function Header() {
  const { user, signOut, loading } = useAuth()

  return (
    <>
      <header className="sticky top-0 z-40 bg-white border-b-2 border-black">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3 group">
            <div className="w-9 h-9 bg-black flex items-center justify-center group-hover:bg-white group-hover:outline group-hover:outline-2 group-hover:outline-black transition-all duration-300">
              <span className="text-white font-heading font-black text-base group-hover:text-black transition-colors duration-300">E</span>
            </div>
            <div>
              <h1 className="text-sm font-heading font-black tracking-tight leading-none uppercase">CULTURA ETÉREA</h1>
              <p className="text-[9px] text-black tracking-[0.3em] uppercase leading-none mt-0.5 font-mono">Medellín Labs</p>
            </div>
          </Link>
          <div className="flex items-center gap-4">
            <Navigation />
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