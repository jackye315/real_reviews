import type { AppChromeProps } from '../types/ui'

export function AppChrome({ mode, developerButtonRef, onDeveloperOpen, onNewSearch }: AppChromeProps) {
  return (
    <header className="app-chrome flex min-h-14 items-center justify-between border-b border-[#DED8CE] bg-[#FFFDFC] px-4 sm:px-6">
      <button
        onClick={onNewSearch}
        className="min-h-11 text-sm font-semibold uppercase tracking-[0.28em] text-[#B7462D] hover:text-[#9F3C27] focus:outline-none"
        aria-label="Go home"
      >
        Real Reviews
      </button>
      <div className="flex items-center gap-3">
        {mode === 'workspace' && (
          <button onClick={onNewSearch} className="min-h-11 px-2 text-sm text-[#4B5A63] hover:text-[#35647C]">
            New search
          </button>
        )}
        <button
          ref={developerButtonRef}
          onClick={onDeveloperOpen}
          className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-md p-2 text-[#6B7378] hover:bg-[#F1ECE4] hover:text-[#24313A] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#B7462D]"
          aria-label="Developer"
          title="Developer"
        >
          <svg
            aria-hidden="true"
            className="h-5 w-5"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="m8 9-3 3 3 3" />
            <path d="m16 9 3 3-3 3" />
            <path d="m14 6-4 12" />
          </svg>
        </button>
      </div>
    </header>
  )
}
