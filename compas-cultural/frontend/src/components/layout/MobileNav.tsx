import { Link, useLocation } from 'react-router-dom'

const LINKS = [
  { to: '/cerca-de-ti', label: 'CERCA', icon: '📍' },
  { to: '/agenda', label: 'AGENDA', icon: '▲' },
  { to: '/colectivos', label: 'COLECTIVO', icon: '◇' },
  { to: '/nosotros', label: 'NOSOTROS', icon: 'M' },
  { to: '/aportes', label: 'VAKI', icon: '♥' },
]

export default function MobileNav() {
  const { pathname } = useLocation()

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t-2 border-black pb-[env(safe-area-inset-bottom)] z-50">
      <div className="flex">
        {LINKS.map(({ to, label, icon }) => {
          const basePath = to.split('#')[0]
          const active = basePath === '/' ? pathname === '/' : pathname.startsWith(basePath)
          return (
            <Link
              key={to}
              to={to}
              className={lex-1 flex flex-col items-center justify-center gap-0.5 pt-2 pb-1.5 text-[8px] sm:text-[9px] font-mono font-bold uppercase tracking-wider transition-all duration-200  + (active ? 'text-white bg-black' : 'text-black')}
            >
              <span className="text-sm">{icon}</span>
              {label}
            </Link>
          )
        })}
      </div>
    </nav>
  )
}
