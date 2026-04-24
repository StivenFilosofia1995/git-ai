import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from 'react'
import type { User, Session } from '@supabase/supabase-js'
import { supabase } from './supabase'
import { obtenerPerfil, crearPerfil } from './api'

interface AuthState {
  user: User | null
  session: Session | null
  loading: boolean
  perfilCompleto: boolean
  perfilLoading: boolean
  marcarPerfilCompleto: () => void
  signUp: (
    email: string,
    password: string,
    metadata?: Record<string, string | boolean>
  ) => Promise<{ error: string | null }>
  signIn: (email: string, password: string) => Promise<{ error: string | null }>
  signInWithGoogle: () => Promise<{ error: string | null }>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthState | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)
  const [perfilCompleto, setPerfilCompleto] = useState(true)
  const [perfilLoading, setPerfilLoading] = useState(false)

  const checkPerfil = useCallback(async (userId: string) => {
    setPerfilLoading(true)
    try {
      await obtenerPerfil(userId)
      setPerfilCompleto(true)
    } catch {
      setPerfilCompleto(false)
    } finally {
      setPerfilLoading(false)
    }
  }, [])

  const marcarPerfilCompleto = useCallback(() => {
    setPerfilCompleto(true)
  }, [])

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session: s } }) => {
      setSession(s)
      setUser(s?.user ?? null)
      if (s?.user) {
        checkPerfil(s.user.id)
      }
      setLoading(false)
    })

    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, s) => {
      setSession(s)
      setUser(s?.user ?? null)

      if (event === 'SIGNED_IN' && s?.user) {
        // Try to create profile from pending localStorage data (email registration flow)
        const pendingRaw = localStorage.getItem('eterea_pending_profile')
        if (pendingRaw) {
          const pendingData = JSON.parse(pendingRaw)
          crearPerfil(pendingData, s.user.id)
            .then(() => {
              localStorage.removeItem('eterea_pending_profile')
              setPerfilCompleto(true)
            })
            .catch(() => {
              // Profile might already exist or data is invalid — check normally
            })
        }

        // Check if profile exists
        checkPerfil(s.user.id)

        // Send welcome email ONLY on first sign-in (avoid duplicates)
        const createdAt = new Date(s.user.created_at).getTime()
        const now = Date.now()
        const isNewUser = now - createdAt < 60_000 // created less than 60s ago
        if (isNewUser) {
          const email = s.user.email
          if (email) {
            fetch(`${import.meta.env.VITE_API_BASE_URL ?? '/api/v1'}/auth/welcome-email`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ email, nombre: s.user.user_metadata?.full_name }),
            }).catch((err) => console.warn('Welcome email failed:', err))
          }
        }
      }

      if (event === 'SIGNED_OUT') {
        setPerfilCompleto(true)
      }
    })

    return () => subscription.unsubscribe()
  }, [checkPerfil])

  const signUp = async (
    email: string,
    password: string,
    metadata?: Record<string, string | boolean>
  ) => {
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: metadata ? { data: metadata } : undefined,
    })
    return { error: error?.message ?? null }
  }

  const signIn = async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    return { error: error?.message ?? null }
  }

  const signInWithGoogle = async () => {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin },
    })
    return { error: error?.message ?? null }
  }

  const signOut = async () => {
    await supabase.auth.signOut()
  }

  return (
    <AuthContext.Provider value={{ user, session, loading, perfilCompleto, perfilLoading, marcarPerfilCompleto, signUp, signIn, signInWithGoogle, signOut }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
