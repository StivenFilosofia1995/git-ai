import { useState, useEffect } from 'react'
import { Helmet } from 'react-helmet-async'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/AuthContext'
import { supabase } from '../lib/supabase'

export default function ResetPassword() {
  const { updatePassword } = useAuth()
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [ready, setReady] = useState(false)

  // Supabase envía el token en el hash de la URL — escuchar el evento PASSWORD_RECOVERY
  useEffect(() => {
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event) => {
      if (event === 'PASSWORD_RECOVERY') setReady(true)
    })
    return () => subscription.unsubscribe()
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    if (password.length < 6) { setError('La contraseña debe tener al menos 6 caracteres'); return }
    if (password !== confirm) { setError('Las contraseñas no coinciden'); return }
    setLoading(true)
    const { error: err } = await updatePassword(password)
    setLoading(false)
    if (err) { setError(err); return }
    navigate('/', { replace: true })
  }

  if (!ready) {
    return (
      <div className="max-w-md mx-auto px-6 py-20 text-center">
        <div className="border-2 border-black p-10">
          <div className="w-8 h-8 border-2 border-black border-t-transparent animate-spin mx-auto mb-4" />
          <p className="font-mono text-sm opacity-60">Verificando enlace…</p>
          <p className="font-mono text-xs opacity-40 mt-2">Si nada ocurre, revisá que el enlace del email no haya expirado.</p>
        </div>
      </div>
    )
  }

  return (
    <>
      <Helmet>
        <title>Nueva contraseña — Cultura ETÉREA</title>
      </Helmet>
      <div className="max-w-md mx-auto px-6 py-20">
        <div className="text-center mb-10">
          <div className="w-12 h-12 bg-black flex items-center justify-center mx-auto mb-4">
            <span className="text-white font-heading font-bold text-lg">E</span>
          </div>
          <h1 className="text-2xl font-heading font-black tracking-tight mb-1 uppercase">
            Nueva contraseña
          </h1>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-xs font-mono font-bold uppercase tracking-wider mb-1.5">
              Nueva contraseña
            </label>
            <input
              type="password"
              required
              minLength={6}
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="Mínimo 6 caracteres"
              className="w-full border-2 border-black focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] px-4 py-3 text-sm font-mono outline-none transition-all"
            />
          </div>

          <div>
            <label className="block text-xs font-mono font-bold uppercase tracking-wider mb-1.5">
              Confirmar contraseña
            </label>
            <input
              type="password"
              required
              value={confirm}
              onChange={e => setConfirm(e.target.value)}
              placeholder="Repetí la contraseña"
              className="w-full border-2 border-black focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] px-4 py-3 text-sm font-mono outline-none transition-all"
            />
          </div>

          {error && (
            <p className="text-sm font-mono border-2 border-black px-4 py-3">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-black text-white font-mono font-bold text-sm uppercase tracking-wider py-3.5 hover:bg-neutral-800 transition-all disabled:opacity-50"
          >
            {loading ? '...' : 'Guardar nueva contraseña'}
          </button>
        </form>
      </div>
    </>
  )
}
