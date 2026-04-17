import { Link } from 'react-router-dom'

export default function Footer() {
  return (
    <footer className="border-t-2 border-black py-10 mt-0 mb-16 md:mb-0 bg-white">
      <div className="max-w-7xl mx-auto px-6">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-black flex items-center justify-center">
              <span className="text-white font-heading font-black text-xs">E</span>
            </div>
            <span className="text-sm font-heading font-black uppercase tracking-wider">Cultura ETÉREA</span>
          </div>
          <div className="flex items-center gap-6">
            {['Explorar', 'Agenda', 'Mapa', 'Registrar'].map(label => (
              <Link
                key={label}
                to={`/${label.toLowerCase()}`}
                className="text-[11px] font-mono font-bold uppercase tracking-wider text-black hover:underline underline-offset-4 transition-all"
              >
                {label}
              </Link>
            ))}
          </div>
          <p className="text-[11px] font-mono font-bold uppercase tracking-wider text-black">
            Medellín · Valle de Aburrá · 2026
          </p>
        </div>
      </div>
    </footer>
  )
}