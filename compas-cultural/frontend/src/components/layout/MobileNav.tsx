import { Link, useLocation } from 'react-router-dom'

const LINKS = [
  { to: '/', label: 'INICIO', icon: '■' },
  { to: '/explorar', label: 'EXPLORAR', icon: '◆' },
  { to: '/agenda', label: 'AGENDA', icon: '▲' },
  { to: '/colectivos', label: 'COLECTIVOS', icon: '◇' },
  { to: '/nosotros', label: 'NOSOTROS', icon: '●' },
]

export default function MobileNav() {
  const { pathname } = useLocation()

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t-2 border-black pb-[env(safe-area-inset-bottom)] z-50">
      <div className="flex">
        {LINKS.map(({ to, label, icon }) => {
          const active = to === '/' ? pathname === '/' : pathname.startsWith(to)
          return (
            <Link
              key={to}
              to={to}
              className={`flex-1 flex flex-col items-center gap-0.5 py-2.5 text-[9px] font-mono font-bold uppercase tracking-wider transition-all duration-200 ${
                active
                  ? 'text-white bg-black'
                  : 'text-black'
              }`}
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