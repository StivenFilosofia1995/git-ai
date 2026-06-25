import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../lib/AuthContext'

interface RequireAuthProps {
  children: React.ReactNode
}

/**
 * Envuelve cualquier ruta que requiera sesión activa.
 * Si el usuario no está logueado, redirige a /login con `state.from`
 * para que después del login vuelva a la misma página.
 */
export default function RequireAuth({ children }: RequireAuthProps) {
  const { user, loading } = useAuth()
  const location = useLocation()

  // Mientras se carga el estado de sesión, no renderizar nada para evitar flash
  if (loading) return null

  if (!user) {
    return (
      <Navigate
        to="/login"
        state={{ from: location.pathname }}
        replace
      />
    )
  }

  return <>{children}</>
}
