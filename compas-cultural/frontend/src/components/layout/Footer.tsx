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
          <div className="flex flex-col items-start md:items-end gap-2">
            <a
              href="https://vaki.co/es/vaki/O9pVekXen6m94eLNwMzp"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 px-4 py-2 border-2 border-black bg-yellow-300 text-black text-[11px] font-mono font-bold uppercase tracking-wider hover:bg-yellow-400 transition-all duration-200"
            >
              ♥ Apoyar en Vaki
            </a>
            <p className="text-[10px] font-mono text-black/60 uppercase tracking-wider">
              Ayudanos a sostener y mejorar la plataforma
            </p>
          </div>
        </div>
      </div>
    </footer>
  )
}