interface ChatSuggestionsProps {
  onSelect: (suggestion: string) => void
}

export default function ChatSuggestions({ onSelect }: Readonly<ChatSuggestionsProps>) {
  const suggestions = [
    '¿Qué hay hoy en el centro?',
    'Eventos de jazz esta semana',
    'Dónde ver teatro independiente',
    'Freestyle rap esta noche',
    'Librerías cerca de Laureles',
    'Arte contemporáneo en El Poblado'
  ]

  return (
    <div className="space-y-2">
      <p className="text-xs font-mono font-bold uppercase tracking-wider">Sugerencias:</p>
      <div className="space-y-1">
        {suggestions.map((suggestion) => (
          <button
            key={suggestion}
            onClick={() => onSelect(suggestion)}
            className="block w-full text-left text-xs hover:underline p-1 font-mono"
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  )
}