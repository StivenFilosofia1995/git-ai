interface SearchSuggestionsProps {
  suggestions: string[]
  onSelect: (suggestion: string) => void
}

export default function SearchSuggestions({ suggestions, onSelect }: SearchSuggestionsProps) {
  if (suggestions.length === 0) return null

  return (
    <div className="absolute top-full left-0 right-0 bg-white border border-gray-200 border-t-0 z-10">
      {suggestions.map((suggestion, index) => (
        <button
          key={index}
          onClick={() => onSelect(suggestion)}
          className="w-full text-left px-4 py-2 hover:bg-gray-50 text-sm"
        >
          {suggestion}
        </button>
      ))}
    </div>
  )
}