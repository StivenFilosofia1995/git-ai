import { Link, useLocation } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/', label: 'Hoy', match: (p: string) => p === '/' || p.startsWith('/agenda') },
  { to: '/mapa', label: 'Mapa', match: (p: string) => p.startsWith('/mapa') },
  { to: '/cerca-de-ti', label: 'Cerca de mí', match: (p: string) => p.startsWith('/cerca-de-ti') },
  { to: '/colectivos', label: 'Colectivos', match: (p: string) => p.startsWith('/colectivos') },
]

export default function Navigation() {
  const { pathname } = useLocation()

  return (
    <nav aria-label="Navegación principal" className="hidden md:flex items-center">
      {NAV_ITEMS.map(({ to, label, match }) => {
        const active = match(pathname)
        return (
          <Link
            key={to}
            to={to}
            aria-current={active ? 'page' : undefined}
            className={`px-3 lg:px-4 py-2 text-sm font-bold border-b-2 transition-colors ${
              active ? 'border-black text-black' : 'border-transparent text-black/55 hover:text-black hover:border-black'
            }`}
          >
            {label}
          </Link>
        )
      })}
    </nav>
  )
}
