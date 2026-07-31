import type { SearchFormProps } from '../types/ui'

export function SearchForm({ searchQuery, setSearchQuery, onSubmit, isSearching, compact = false }: SearchFormProps) {
  return (
    <form className="flex gap-2" onSubmit={onSubmit}>
      <input
        value={searchQuery}
        onChange={(event) => setSearchQuery(event.target.value)}
        className="min-h-11 min-w-0 flex-1 rounded-xl border border-[#CFC6BA] bg-[#FFFDFC] px-3 py-2 text-[#24313A] outline-none ring-[#B7462D] focus:ring-2"
        placeholder={compact ? 'Free-form search…' : 'pizza in Queens, quiet sushi near me…'}
        aria-label="Free-form restaurant search"
      />
      <button disabled={isSearching} className="min-h-11 rounded-xl bg-[#B7462D] px-4 py-2 font-semibold text-[#FFFDFC] hover:bg-[#9F3C27] disabled:opacity-50">
        {isSearching ? 'Go…' : 'Go'}
      </button>
    </form>
  )
}
