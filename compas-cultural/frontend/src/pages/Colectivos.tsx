import { Helmet } from 'react-helmet-async'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getEspacios, type Espacio } from '../lib/api'
import { useAuth } from '../lib/AuthContext'

const TIPOS_COLECTIVO = [
  { value: '', label: 'Todos' },
  { value: 'hip_hop', label: 'Hip-Hop' },
  { value: 'teatro', label: 'Teatro' },
  { value: 'danza', label: 'Danza' },
  { value: 'musica_en_vivo', label: 'Música' },
  { value: 'arte_contemporaneo', label: 'Arte' },
  { value: 'poesia', label: 'Poesía' },
  { value: 'editorial', label: 'Editorial' },
  { value: 'fotografia', label: 'Fotografía' },
  { value: 'muralismo', label: 'Muralismo' },
]

export default function Colectivos() {
  const { user } = useAuth()
  const [colectivos, setColectivos] = useState<Espacio[]>([])
  const [filtro, setFiltro] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    getEspacios({ limit: 100, categoria: filtro || undefined })
      .then(list => {
        // Filter by tipo colectivo or broader search
        setColectivos(list)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [filtro])

  return (
    <>
      <Helmet>
        <title>Colectivos Culturales — Cultura ETÉREA</title>
        <meta name="description" content="Colectivos culturales activos en el Valle de Aburrá" />
      </Helmet>

      {/* HERO */}
      <section className="bg-white border-b-2 border-black">
        <div className="max-w-7xl mx-auto px-6 py-16 lg:py-24">
          <div className="max-w-2xl">
            <div className="flex items-center gap-3 mb-6">
              <span className="w-3 h-3 bg-black" />
              <span className="text-[11px] tracking-[0.3em] uppercase font-mono font-bold">
                Ecosistema cultural · Valle de Aburrá
              </span>
            </div>
            <h1 className="text-4xl md:text-6xl font-heading font-black tracking-tighter uppercase leading-[0.9] mb-6">
              Colectivos<br />
              <span style={{ WebkitTextStroke: '2px black', WebkitTextFillColor: 'transparent' }}>
                Culturales
              </span>
            </h1>
            <p className="text-sm font-mono leading-relaxed max-w-md mb-8">
              Proyectos independientes, colectivos artísticos, escuelas de formación
              y organizaciones culturales activas en Medellín y el Área Metropolitana.
              Todos conectados al sistema de escucha en tiempo real.
            </p>

            <div className="flex flex-wrap gap-4">
              <Link
                to="/registrar"
                className="inline-flex items-center gap-2 bg-black text-white px-6 py-3 font-mono text-xs font-bold uppercase tracking-wider hover:bg-white hover:text-black border-2 border-black transition-all duration-300"
              >
                Registrar mi colectivo
                <span>→</span>
              </Link>
              <span className="inline-flex items-center px-4 py-3 border-2 border-black font-mono text-xs font-bold uppercase tracking-wider">
                {colectivos.length} activos
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* FILTROS */}
      <div className="border-b-2 border-black bg-white">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center gap-2 overflow-x-auto pb-1">
            <span className="text-[9px] font-mono font-bold uppercase tracking-wider opacity-40 shrink-0">Filtrar:</span>
            {TIPOS_COLECTIVO.map(t => (
              <button
                key={t.value}
                onClick={() => setFiltro(t.value)}
                className={`px-3 py-1.5 text-[10px] font-mono font-bold uppercase tracking-wider border-2 border-black transition-all duration-200 shrink-0 ${
                  filtro === t.value ? 'bg-black text-white' : 'hover:bg-black/5'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* GRID */}
      <div className="max-w-7xl mx-auto px-6 py-12">
        {loading ? (
          <div className="text-center py-20">
            <div className="w-8 h-8 border-2 border-black/20 border-t-black animate-spin mx-auto" />
            <p className="text-xs font-mono mt-4 opacity-50">Cargando colectivos...</p>
          </div>
        ) : colectivos.length === 0 ? (
          <div className="text-center py-20 border-2 border-black">
            <p className="text-sm font-mono mb-4">No hay colectivos registrados con ese filtro.</p>
            <Link to="/registrar" className="text-sm font-mono font-bold uppercase tracking-wider hover:underline">
              Registrar el primero →
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-0 border-2 border-black">
            {colectivos.map((col, i) => (
              <Link
                key={col.id}
                to={`/espacio/${col.slug}`}
                className="group border-b-2 border-r-2 border-black p-6 hover:bg-black hover:text-white transition-all duration-300"
              >
                <div className="flex items-start justify-between mb-3">
                  <span className="text-[10px] font-mono font-bold opacity-40 group-hover:opacity-100 tracking-wider">
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <span className="text-[9px] font-mono font-bold uppercase tracking-wider border border-current px-2 py-0.5">
                    {col.categoria_principal.replaceAll('_', ' ')}
                  </span>
                </div>

                <h3 className="font-heading font-black text-lg uppercase tracking-wide leading-tight mb-2">
                  {col.nombre}
                </h3>

                {col.descripcion_corta && (
                  <p className="text-xs font-mono leading-relaxed opacity-60 group-hover:opacity-80 line-clamp-2 mb-3">
                    {col.descripcion_corta}
                  </p>
                )}

                <div className="flex items-center gap-3 text-[10px] font-mono opacity-50 group-hover:opacity-100">
                  {col.barrio && <span>◉ {col.barrio}</span>}
                  <span>{col.municipio}</span>
                  {col.instagram_handle && <span>@{col.instagram_handle}</span>}
                </div>

                <div className="flex items-center gap-2 mt-3">
                  <span className={`w-2 h-2 rounded-full ${
                    col.nivel_actividad === 'muy_activo' ? 'bg-green-500 animate-pulse' :
                    col.nivel_actividad === 'activo' ? 'bg-green-400' :
                    col.nivel_actividad === 'moderado' ? 'bg-yellow-400' : 'bg-gray-400'
                  }`} />
                  <span className="text-[9px] font-mono font-bold uppercase tracking-wider opacity-50 group-hover:opacity-80">
                    {col.nivel_actividad?.replaceAll('_', ' ')}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* CTA */}
      <div className="max-w-7xl mx-auto px-6 pb-16">
        <div className="bg-black text-white p-10 md:p-16 border-2 border-black relative overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 border-2 border-white/10 rounded-full -translate-y-1/2 translate-x-1/2" />
          <div className="relative z-10 max-w-lg">
            <h2 className="text-2xl md:text-4xl font-heading font-black uppercase tracking-tighter mb-4 leading-[0.95]">
              ¿Tenés un colectivo cultural?
            </h2>
            <p className="text-sm font-mono mb-8 opacity-80 leading-relaxed">
              Registrá tu colectivo pegando tu link de Instagram o web.
              Nuestro sistema extraerá la información automáticamente
              y quedará conectado al scraping activo — actualizamos tus eventos cada 6 horas.
            </p>
            <div className="flex flex-wrap gap-4">
              <Link
                to="/registrar"
                className="inline-flex items-center gap-2 bg-white text-black px-6 py-3 font-mono text-xs font-bold uppercase tracking-wider hover:bg-black hover:text-white hover:outline hover:outline-2 hover:outline-white transition-all duration-300"
              >
                Registrar colectivo →
              </Link>
              {!user && (
                <Link
                  to="/login"
                  className="inline-flex items-center gap-2 border-2 border-white px-6 py-3 font-mono text-xs font-bold uppercase tracking-wider hover:bg-white hover:text-black transition-all duration-300"
                >
                  Crear cuenta primero
                </Link>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
