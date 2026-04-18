import { useState, useEffect } from 'react'
import { getResenas, getResenaStats, crearResena, type Resena, type ResenaStats } from '../../lib/api'
import { useAuth } from '../../lib/AuthContext'

interface Props {
  tipo: 'evento' | 'espacio'
  itemId: string
  itemNombre: string
}

function StarRating({ value, onChange, readonly = false }: { value: number; onChange?: (v: number) => void; readonly?: boolean }) {
  const [hover, setHover] = useState(0)
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map(star => (
        <button
          key={star}
          type="button"
          disabled={readonly}
          onClick={() => onChange?.(star)}
          onMouseEnter={() => !readonly && setHover(star)}
          onMouseLeave={() => setHover(0)}
          className={`text-lg transition-all ${readonly ? 'cursor-default' : 'cursor-pointer hover:scale-110'}`}
        >
          <span className={`${(hover || value) >= star ? 'opacity-100' : 'opacity-20'}`}>★</span>
        </button>
      ))}
    </div>
  )
}

function StatsBar({ stats }: { stats: ResenaStats }) {
  if (stats.total === 0) return null
  return (
    <div className="flex items-center gap-4 py-3 px-4 border-2 border-black bg-black/[0.02]">
      <div className="text-center">
        <div className="text-2xl font-heading font-black">{stats.promedio}</div>
        <StarRating value={Math.round(stats.promedio)} readonly />
        <div className="text-[10px] font-mono opacity-50 mt-1">{stats.total} reseña{stats.total !== 1 ? 's' : ''}</div>
      </div>
      <div className="flex-1 space-y-1">
        {[5, 4, 3, 2, 1].map(n => {
          const count = stats.distribucion[String(n)] || 0
          const pct = stats.total > 0 ? (count / stats.total) * 100 : 0
          return (
            <div key={n} className="flex items-center gap-2 text-[10px] font-mono">
              <span className="w-3 text-right">{n}</span>
              <span className="opacity-40">★</span>
              <div className="flex-1 h-2 bg-black/10 border border-black/20">
                <div className="h-full bg-black transition-all duration-500" style={{ width: `${pct}%` }} />
              </div>
              <span className="w-6 text-right opacity-50">{count}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default function ReviewSection({ tipo, itemId, itemNombre }: Props) {
  const { user } = useAuth()
  const [resenas, setResenas] = useState<Resena[]>([])
  const [stats, setStats] = useState<ResenaStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  // Form state
  const [puntuacion, setPuntuacion] = useState(0)
  const [titulo, setTitulo] = useState('')
  const [comentario, setComentario] = useState('')

  useEffect(() => {
    Promise.all([
      getResenas(tipo, itemId),
      getResenaStats(tipo, itemId),
    ])
      .then(([r, s]) => {
        setResenas(r)
        setStats(s)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [tipo, itemId])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!user || puntuacion === 0 || !comentario.trim()) return
    setSubmitting(true)
    setError('')
    try {
      const nueva = await crearResena(
        { tipo, item_id: itemId, puntuacion, titulo: titulo || undefined, comentario },
        user.id,
        user.user_metadata?.full_name || user.email?.split('@')[0]
      )
      setResenas(prev => [nueva, ...prev])
      setStats(prev => prev ? {
        ...prev,
        total: prev.total + 1,
        promedio: Math.round(((prev.promedio * prev.total) + puntuacion) / (prev.total + 1) * 10) / 10,
        distribucion: { ...prev.distribucion, [String(puntuacion)]: (prev.distribucion[String(puntuacion)] || 0) + 1 },
      } : prev)
      setShowForm(false)
      setPuntuacion(0)
      setTitulo('')
      setComentario('')
    } catch {
      setError('Ya reseñaste este item o hubo un error.')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <div className="py-4 font-mono text-sm opacity-40">Cargando reseñas...</div>

  return (
    <div className="border-t-2 border-black pt-6 mt-8">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-heading font-black text-lg uppercase tracking-wider">
          Opiniones y Experiencias
        </h3>
        {user && !showForm && (
          <button
            onClick={() => setShowForm(true)}
            className="text-[11px] font-mono font-bold uppercase tracking-wider px-3 py-1.5 border-2 border-black hover:bg-black hover:text-white transition-all"
          >
            + Escribir reseña
          </button>
        )}
      </div>

      {/* Stats */}
      {stats && stats.total > 0 && <StatsBar stats={stats} />}

      {/* Write review form */}
      {showForm && user && (
        <form onSubmit={handleSubmit} className="border-2 border-black p-4 mt-4 space-y-3">
          <div className="text-[10px] font-mono font-bold uppercase tracking-wider opacity-50">
            Tu opinión sobre {itemNombre}
          </div>

          <div>
            <label className="block text-[10px] font-mono font-bold uppercase tracking-wider mb-1">Puntuación *</label>
            <StarRating value={puntuacion} onChange={setPuntuacion} />
          </div>

          <div>
            <label className="block text-[10px] font-mono font-bold uppercase tracking-wider mb-1">Título (opcional)</label>
            <input
              type="text"
              value={titulo}
              onChange={e => setTitulo(e.target.value)}
              maxLength={100}
              placeholder="Resumí tu experiencia en una frase"
              className="w-full px-3 py-2 border-2 border-black text-sm font-mono focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-[10px] font-mono font-bold uppercase tracking-wider mb-1">Tu experiencia *</label>
            <textarea
              value={comentario}
              onChange={e => setComentario(e.target.value)}
              minLength={5}
              maxLength={2000}
              rows={4}
              placeholder="Contanos cómo fue tu experiencia..."
              className="w-full px-3 py-2 border-2 border-black text-sm font-mono focus:outline-none resize-none"
              required
            />
            <div className="text-[9px] font-mono opacity-30 text-right">{comentario.length}/2000</div>
          </div>

          {error && <p className="text-xs font-mono text-red-600">{error}</p>}

          <div className="flex gap-2">
            <button
              type="submit"
              disabled={submitting || puntuacion === 0 || comentario.length < 5}
              className="px-4 py-2 bg-black text-white text-[11px] font-mono font-bold uppercase tracking-wider hover:bg-white hover:text-black border-2 border-black transition-all disabled:opacity-30"
            >
              {submitting ? 'Enviando...' : 'Publicar reseña'}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="px-4 py-2 text-[11px] font-mono font-bold uppercase tracking-wider border-2 border-black hover:bg-black hover:text-white transition-all"
            >
              Cancelar
            </button>
          </div>
        </form>
      )}

      {!user && (
        <p className="text-sm font-mono opacity-40 mt-2">
          Iniciá sesión para dejar tu reseña.
        </p>
      )}

      {/* Reviews list */}
      <div className="space-y-3 mt-4">
        {resenas.length === 0 && (
          <p className="text-sm font-mono opacity-40 py-4">
            Todavía no hay reseñas. ¡Sé el primero en opinar!
          </p>
        )}
        {resenas.map(r => {
          const fecha = new Date(r.created_at)
          const fechaStr = fecha.toLocaleDateString('es-CO', { day: 'numeric', month: 'short', year: 'numeric' })
          return (
            <div key={r.id} className="border border-black/20 p-3">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 bg-black text-white flex items-center justify-center text-[10px] font-bold">
                    {(r.user_nombre || '?')[0].toUpperCase()}
                  </div>
                  <span className="text-[11px] font-mono font-bold">{r.user_nombre || 'Anónimo'}</span>
                  <StarRating value={r.puntuacion} readonly />
                </div>
                <span className="text-[9px] font-mono opacity-40">{fechaStr}</span>
              </div>
              {r.titulo && <p className="text-sm font-heading font-bold mt-1">{r.titulo}</p>}
              <p className="text-sm font-mono mt-1 whitespace-pre-line">{r.comentario}</p>
            </div>
          )
        })}
      </div>
    </div>
  )
}
