export default function EtereaThinking({ compact = false }: Readonly<{ compact?: boolean }>) {
  return (
    <div className={`border-2 border-black bg-white ${compact ? 'p-3' : 'p-4'} relative overflow-hidden`}>
      <div className="absolute inset-0 bg-[linear-gradient(120deg,transparent_0%,rgba(0,0,0,0.05)_35%,transparent_70%)] animate-[pulse_1.8s_ease-in-out_infinite]" />
      <div className="relative flex items-center gap-3">
        <div className="relative w-10 h-10 border-2 border-black bg-white flex items-center justify-center shrink-0">
          <img src="/icons/favicon.svg" alt="ETEREA" className="w-5 h-5 object-contain" />
          <span className="absolute -top-1 -right-1 w-2 h-2 bg-black rounded-full animate-pulse" />
        </div>
        <div className="min-w-0">
          <p className={`font-mono font-bold uppercase tracking-[0.22em] ${compact ? 'text-[10px]' : 'text-[11px]'}`}>
            ETEREA esta pensando
          </p>
          <div className="flex items-center gap-1 mt-1">
            <span className="w-1.5 h-1.5 bg-black rounded-full animate-bounce [animation-delay:-0.2s]" />
            <span className="w-1.5 h-1.5 bg-black rounded-full animate-bounce [animation-delay:-0.05s]" />
            <span className="w-1.5 h-1.5 bg-black rounded-full animate-bounce [animation-delay:0.1s]" />
          </div>
        </div>
      </div>
    </div>
  )
}
