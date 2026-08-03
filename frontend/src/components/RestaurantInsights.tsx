import { useEffect, useState } from 'react'
import { streamDishSummary } from '../lib/api'
import type { Review } from '../types/api'

const MAX_REVIEWS = 50

type Props = {
  placeId: string
  initialDishSummary?: string | null
  visibleReviews: Review[]
}

export function RestaurantInsights({ placeId, initialDishSummary, visibleReviews }: Props) {
  const [dishSummary, setDishSummary] = useState<string | null>(initialDishSummary ?? null)
  const [requestedCount, setRequestedCount] = useState(10)
  const [dishPending, setDishPending] = useState(false)
  const [dishError, setDishError] = useState<string | null>(null)


  useEffect(() => {
    setDishSummary(initialDishSummary ?? null)
    setRequestedCount(10)
    setDishError(null)

  }, [placeId, initialDishSummary])

  const generate = async () => {
    if (requestedCount > visibleReviews.length) {
      setDishError(`Only ${visibleReviews.length} loaded review${visibleReviews.length === 1 ? '' : 's'} are available. Show more saved reviews first.`)
      return
    }
    const texts = visibleReviews.slice(0, requestedCount)
      .map((review) => review.text || review.original_text || '')
    const previousSummary = dishSummary
    let streamedText = ''
    setDishPending(true)
    setDishError(null)
    try {
      const result = await streamDishSummary(placeId, texts, (delta) => {
        streamedText += delta
        setDishSummary(streamedText)
      })
      setDishSummary(result.summary)
    } catch (error) {
      setDishSummary(previousSummary)
      setDishError(error instanceof Error ? error.message : 'The local LLM isn’t available. Try again later.')
    } finally {
      setDishPending(false)
    }
  }

  return (
    <section className="space-y-3" aria-label="Restaurant insights">
      <section className="rounded-xl border border-[#DED8CE] bg-[#FFFDFC] p-4" aria-labelledby="local-dish-summary-heading">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between lg:gap-6">
          <h2 id="local-dish-summary-heading" className="shrink-0 font-semibold">Local dish summary</h2>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <label className="flex items-center gap-2 text-sm font-medium">
              Reviews to include
              <input
                type="number"
                min={1}
                max={MAX_REVIEWS}
                value={requestedCount}
                onChange={(event) => setRequestedCount(Math.max(1, Math.min(MAX_REVIEWS, Number(event.target.value) || 1)))}
                className="min-h-11 w-full rounded-lg border border-[#CFC6BA] bg-white px-3 sm:w-28"
              />
            </label>
            <button type="button" disabled={dishPending || !visibleReviews.length} onClick={generate} className="min-h-11 whitespace-nowrap rounded-xl bg-[#B7462D] px-4 py-2 text-sm font-semibold text-[#FFFDFC] disabled:opacity-50">
              {dishPending ? 'Generating…' : dishSummary ? 'Replace summary' : 'Generate summary'}
            </button>
          </div>
        </div>
        {dishSummary && <p className="mt-3 whitespace-pre-wrap text-sm leading-6">{dishSummary}{dishPending && <span aria-hidden="true" className="ml-0.5 animate-pulse">▍</span>}</p>}
        {dishPending && !dishSummary && <p role="status" className="mt-3 text-sm text-[#6B7378]">Starting local LLM…</p>}
        {dishError && <p role="status" className="mt-2 text-sm text-[#8E321F]">{dishError}</p>}
      </section>
    </section>
  )
}
