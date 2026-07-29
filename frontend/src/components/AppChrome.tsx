import type { AppChromeProps } from '../types/ui'

export function AppChrome({ mode, developerButtonRef, onDeveloperOpen, onNewSearch }: AppChromeProps) {
  return (
    <header className="flex h-14 items-center justify-between border-b border-[#DED8CE] bg-[#FFFDFC] px-4 sm:px-6">
      <button
        onClick={onNewSearch}
        className="text-sm font-semibold uppercase tracking-[0.28em] text-[#B7462D] hover:text-[#9F3C27] focus:outline-none"
        aria-label="Go home"
      >
        Real Reviews
      </button>
      <div className="flex items-center gap-3">
        {mode === 'workspace' && (
          <button onClick={onNewSearch} className="text-sm text-[#4B5A63] hover:text-[#35647C]">
            New search
          </button>
        )}
        <button
          ref={developerButtonRef}
          onClick={onDeveloperOpen}
          className="rounded-full p-2 text-lg leading-none text-[#6B7378] hover:bg-[#F1ECE4] hover:text-[#24313A] focus:outline-none focus:ring-2 focus:ring-[#B7462D]"
          aria-label="Developer"
          title="Developer"
        >
          ⚙
        </button>
      </div>
    </header>
  )
}
