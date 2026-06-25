import { useState } from 'react'
import { Helmet } from 'react-helmet-async'
import { Link } from 'react-router-dom'
import { useAuth } from '../lib/AuthContext'

export default function ForgotPassword() {
  const { resetPassword } = useAuth()
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    const { error: err } = await resetPassword(email)
    setLoading(false)
    if (err) { setError(err); return }
    setSent(true)
  }

  return (
    <>
      <Helmet>
        <title>Recuperar contraseña — Cultura ETÉREA</title>
      </Helmet>
      <div className="max-w-md mx-auto px-6 py-20">
        <div className="text-center mb-10">
          <div className="w-12 h-12 bg-black flex items-center justify-center mx-auto mb-4">
            <span className="text-white font-heading font-bold text-lg">E</span>
          </div>
          <h1 className="text-2xl font-heading font-black tracking-tight mb-1 uppercase">
            Recuperar contraseña
          </h1>
          <p className="text-sm font-mono uppercase tracking-wider opacity-60">Cultura ETÉREA · Medellín</p>
        </div>

        {sent ? (
          <div className="border-2 border-black p-10 text-center">
            <span className="text-4xl mb-4 block">✉️</span>
            <h2 className="text-xl font-heading font-black mb-3 uppercase">Revisá tu email</h2>
            <p className="text-sm font-mono mb-6 opacity-70">
              Si <strong>{email}</strong> tiene una cuenta, recibirás un enlace para restablecer tu contraseña.
            </p>
            <Link
              to="/login"
              className="text-sm font-mono font-bold uppercase tracking-wider hover:underline"
            >
              ← Volver a iniciar sesión
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-xs font-mono font-bold uppercase tracking-wider mb-1.5">
                Email
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="tu@email.com"
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
              {loading ? '...' : 'Enviar enlace de recuperación'}
            </button>

            <div className="text-center">
              <Link
                to="/login"
                className="text-sm font-mono font-bold uppercase tracking-wider hover:underline opacity-60"
              >
                ← Volver
              </Link>
            </div>
          </form>
        )}
      </div>
    </>
  )
}
