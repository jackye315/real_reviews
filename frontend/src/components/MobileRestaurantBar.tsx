type Props = {
  restaurantName: string
  activeFilterCount: number
  onBack: () => void
  onOpenFilters?: () => void
}

export function MobileRestaurantBar({ restaurantName, activeFilterCount, onBack, onOpenFilters }: Props) {
  return (
    <div className="sticky top-0 z-20 flex min-h-14 items-center gap-2 border-b border-[#DED8CE] bg-[#FFFDFC]/95 px-3 py-2 backdrop-blur lg:hidden safe-pt">
      <button
        type="button"
        onClick={onBack}
        className="min-h-11 shrink-0 rounded-xl border border-[#CFC6BA] px-3 text-sm font-medium text-[#24313A]"
      >
        ← Results
      </button>
      <div className="min-w-0 flex-1 truncate text-center text-base font-semibold text-[#24313A]" aria-label={restaurantName}>
        {restaurantName}
      </div>
      {onOpenFilters && <button
        type="button"
        onClick={onOpenFilters}
        className="min-h-11 shrink-0 rounded-xl bg-[#B7462D] px-3 text-sm font-semibold text-[#FFFDFC]"
        aria-label={activeFilterCount ? `Open filters, ${activeFilterCount} active` : 'Open filters'}
      >
        Filters{activeFilterCount ? ` (${activeFilterCount})` : ''}
      </button>}
    </div>
  )
}
