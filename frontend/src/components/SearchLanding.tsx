import { Autocomplete } from './Autocomplete'
import { SearchForm } from './SearchForm'
import type { SearchLandingProps } from '../types/ui'

export function SearchLanding({
  searchQuery,
  setSearchQuery,
  onSubmit,
  onAutocompleteSelected,
  isSearching,
  message
}: SearchLandingProps) {
  return (
    <section className="flex min-h-[calc(100vh-3.5rem)] items-center justify-center px-4 py-10">
      <div className="w-full max-w-2xl rounded-[2rem] border border-[#DED8CE] bg-[#FFFDFC] p-6 sm:p-10">
        <div className="mb-8 text-center">
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">Find a restaurant</h1>
          <p className="mx-auto mt-3 max-w-xl text-[#4B5A63]">
            Search for a restaurant, fetch saved Google-sourced reviews, then filter for what matters.
          </p>
        </div>
        <div className="space-y-5">
          <Autocomplete onSelected={onAutocompleteSelected} />
          <div className="flex items-center gap-3 text-sm text-[#7B746C]">
            <div className="h-px flex-1 bg-[#DED8CE]" />
            or
            <div className="h-px flex-1 bg-[#DED8CE]" />
          </div>
          <SearchForm searchQuery={searchQuery} setSearchQuery={setSearchQuery} onSubmit={onSubmit} isSearching={isSearching} />
          {message && <p className="text-sm text-[#B7462D]">{message}</p>}
        </div>
      </div>
    </section>
  )
}
