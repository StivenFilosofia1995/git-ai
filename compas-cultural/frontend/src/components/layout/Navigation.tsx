import { Link, useLocation } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/explorar#cerca-de-ti', label: 'Cerca de ti' },
  { to: '/agenda', label: 'Agenda' },
  { to: '/colectivos', label: 'Colectivos' },
  { to: '/nosotros', label: 'Nosotros' },
]

export default function Navigation() {
  const { pathname } = useLocation()

  return (
    <nav className="hidden md:flex items-center gap-0">
      {NAV_ITEMS.map(({ to, label }) => {
        const basePath = to.split('#')[0]
        const active = basePath === '/' ? pathname === '/' : pathname.startsWith(basePath)
        return (
          <Link
            key={to}
            to={to}
            className={`px-4 py-2 text-[11px] font-mono font-bold uppercase tracking-[0.15em] border-b-2 transition-all duration-200 ${
              active
                ? 'border-black text-black'
                : 'border-transparent text-black/40 hover:text-black hover:border-black'
            }`}
          >
            {label}
          </Link>
        )
      })}
    </nav>
  )
}