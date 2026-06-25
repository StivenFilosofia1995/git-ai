import { useState, useCallback } from 'react'

const KEY = 'eterea:favoritos'

export interface FavoritoItem {
  id: string
  titulo: string
  slug: string
  fecha_inicio: string
  categoria_principal: string
  nombre_lugar?: string
  barrio?: string
  municipio?: string
  imagen_url?: string
  es_gratuito?: boolean
}

function load(): FavoritoItem[] {
  try { return JSON.parse(localStorage.getItem(KEY) ?? '[]') } catch { return [] }
}

function save(items: FavoritoItem[]) {
  localStorage.setItem(KEY, JSON.stringify(items))
}

export function useFavoritos() {
  const [favoritos, setFavoritos] = useState<FavoritoItem[]>(load)

  const toggle = useCallback((item: FavoritoItem) => {
    setFavoritos(prev => {
      const existe = prev.some(f => f.id === item.id)
      const next = existe ? prev.filter(f => f.id !== item.id) : [item, ...prev]
      save(next)
      return next
    })
  }, [])

  const isSaved = useCallback(
    (id: string) => favoritos.some(f => f.id === id),
    [favoritos],
  )

  return { favoritos, toggle, isSaved }
}
