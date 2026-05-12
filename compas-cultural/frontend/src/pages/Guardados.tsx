import { Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { useFavoritos } from '../lib/useFavoritos'
import { getEventDateParts } from '../lib/datetime'

export default function Guardados() {
  const { favoritos, toggle } = useFavoritos()

  return (
    <>
      <Helmet>
        <title>Guardados — Cultura ETÉREA</title>
      </Helmet>
      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="flex items-baseline justify-between mb-8">
          <div>
            <h1 className="text-2xl font-heading font-black tracking-tight uppercase">Eventos Guardados</h1>
            <p className="text-xs font-mono mt-1 opacity-50 uppercase tracking-wider">
              {favoritos.length === 0 ? 'Ninguno aún' : `${favoritos.length} evento${favoritos.length !== 1 ? 's' : ''}`}
            </p>
          </div>
          {favoritos.length > 0 && (
            <button
              type="button"
              onClick={() => { if (confirm('¿Borrar todos los guardados?')) { localStorage.removeItem('eterea:favoritos'); window.location.reload() } }}
              className="text-[10px] font-mono font-bold uppercase tracking-wider opacity-40 hover:opacity-100 transition-opacity"
            >
              Limpiar todo
            </button>
          )}
        </div>

        {favoritos.length === 0 ? (
          <div className="border-2 border-black p-12 text-center">
            <p className="text-4xl mb-4">♡</p>
            <p className="font-mono text-sm opacity-60 mb-6">
              Guarda eventos tocando el ♡ en cualquier tarjeta
            </p>
            <Link
              to="/agenda"
              className="inline-block px-6 py-3 border-2 border-black font-mono font-bold text-sm uppercase tracking-wider hover:bg-black hover:text-white transition-all"
            >
              Ver agenda →
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {favoritos.map(ev => {
              const fecha = ev.fecha_inicio
                ? new Date(ev.fecha_inicio + 'T00:00:00').toLocaleDateString('es-CO', { weekday: 'short', day: 'numeric', month: 'short' })
                : ''
              const pasado = ev.fecha_inicio < new Date().toISOString().slice(0, 10)
              return (
                <div
                  key={ev.id}
                  className={`flex items-center gap-4 border-2 border-black p-4 hover:bg-black hover:text-white transition-all group ${pasado ? 'opacity-50' : ''}`}
                >
                  {ev.imagen_url && (
                    <img src={ev.imagen_url} alt="" className="w-14 h-14 object-cover border border-black/20 shrink-0 group-hover:opacity-80" />
                  )}
                  <div className="flex-1 min-w-0">
                    <Link to={`/evento/${ev.slug}`} className="block font-heading font-black text-sm uppercase tracking-wide leading-snug truncate">
                      {ev.titulo}
                    </Link>
                    <p className="text-[10px] font-mono mt-0.5 opacity-60 capitalize">
                      {fecha}{ev.nombre_lugar ? ` · ${ev.nombre_lugar}` : ''}{ev.barrio ? `, ${ev.barrio}` : ''}
                    </p>
                    {pasado && <span className="text-[9px] font-mono font-bold opacity-50 uppercase">Ya pasó</span>}
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <a
                      href={`https://wa.me/?text=${encodeURIComponent(`📅 *${ev.titulo}*\n🗓 ${fecha}\nhttps://culturaetereamed.com/evento/${ev.slug}`)}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs opacity-50 hover:opacity-100 transition-opacity"
                      title="Compartir por WhatsApp"
                    >
                      <svg viewBox="0 0 24 24" className="w-4 h-4 fill-current" aria-hidden="true">
                        <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
                      </svg>
                    </a>
                    <button
                      type="button"
                      onClick={() => toggle(ev)}
                      title="Quitar de guardados"
                      className="text-base opacity-60 hover:opacity-100 transition-opacity hover:text-red-500"
                    >
                      ♥
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </>
  )
}
