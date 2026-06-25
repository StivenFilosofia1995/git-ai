interface EmptyStateProps {
  title?: string
  description?: string
  icon?: string
}

export default function EmptyState({
  title = "No hay contenido",
  description = "No se encontró información para mostrar.",
  icon = "📭"
}: EmptyStateProps) {
  return (
    <div className="text-center py-12">
      <div className="text-4xl mb-4">{icon}</div>
      <h3 className="text-lg font-mono font-bold mb-2">{title}</h3>
      <p className="text-sm font-mono">{description}</p>
    </div>
  )
}