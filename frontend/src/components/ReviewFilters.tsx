import type { ReviewFiltersProps } from '../types/ui'

export function ReviewFilters({
  filterText,
  setFilterText,
  minRating,
  setMinRating,
  selectedReviewIds,
  setSelectedReviewIds,
  filterPending,
  canFilter,
  topics,
  onFilter
}: ReviewFiltersProps) {
  return (
    <div className="mt-4 space-y-3">
      {topics.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-[#6B7378]">Mentioned in reviews</p>
          <div className="flex flex-wrap gap-2">
            {topics.map((topic) => (
              <button
                key={topic.provider_topic_id}
                type="button"
                onClick={() => {
                  setFilterText(topic.keyword)
                  onFilter(topic.keyword)
                }}
                className="rounded-full bg-[#FFFDFC] px-3 py-1 text-sm text-[#24313A] hover:bg-[#F1ECE4]"
              >
                {topic.keyword}{topic.mentions !== null && topic.mentions !== undefined ? ` (${topic.mentions})` : ''}
              </button>
            ))}
          </div>
        </div>
      )}
      <div className="grid gap-2 sm:grid-cols-[1fr_auto_auto_auto]">
        <input
          value={filterText}
          onChange={(event) => setFilterText(event.target.value)}
          className="min-w-0 rounded-xl border border-[#CFC6BA] bg-[#FFFDFC] px-3 py-2 text-[#24313A] outline-none ring-[#B7462D] focus:ring-2"
          placeholder="mentions spicy noodles, slow service, good mocktails…"
        />
        <select value={minRating} onChange={(event) => setMinRating(event.target.value)} className="rounded-xl border border-[#CFC6BA] bg-[#FFFDFC] px-3 py-2 text-[#24313A] outline-none ring-[#B7462D] focus:ring-2" aria-label="Minimum rating">
          <option value="">Any rating</option>
          <option value="5">5★ only</option>
          <option value="4">4★+</option>
          <option value="3">3★+</option>
          <option value="2">2★+</option>
          <option value="1">1★+</option>
        </select>
        <button disabled={!filterText || filterPending || !canFilter} onClick={() => onFilter()} className="rounded-xl bg-[#B7462D] px-4 py-2 font-semibold text-[#FFFDFC] hover:bg-[#9F3C27] disabled:opacity-50">
          Filter
        </button>
        {selectedReviewIds && (
          <button onClick={() => setSelectedReviewIds(null)} className="rounded-xl border border-[#CFC6BA] px-4 py-2 text-[#24313A]">
            Clear
          </button>
        )}
      </div>
    </div>
  )
}
