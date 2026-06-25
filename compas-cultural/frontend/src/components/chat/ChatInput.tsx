interface ChatInputProps {
  onSend: (mensaje: string) => void
}

export default function ChatInput({ onSend }: ChatInputProps) {
  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const formData = new FormData(e.currentTarget)
    const mensaje = formData.get('mensaje') as string
    if (mensaje.trim()) {
      onSend(mensaje.trim())
      e.currentTarget.reset()
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <div className="flex">
        <input
          name="mensaje"
          type="text"
          placeholder="Pregunta sobre cultura..."
          className="flex-1 px-3 py-2.5 text-sm font-mono border-0 focus:outline-none bg-white placeholder:text-black/30"
        />
        <button
          type="submit"
          className="px-5 py-2.5 bg-black text-white text-[11px] font-mono font-bold uppercase tracking-wider hover:bg-white hover:text-black border-l-2 border-black transition-all duration-300"
        >
          →
        </button>
      </div>
    </form>
  )
}