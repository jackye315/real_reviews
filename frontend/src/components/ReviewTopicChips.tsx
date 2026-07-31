import type { ReviewTopic } from '../types/api'

type Props = {
  topics: ReviewTopic[]
  disabled?: boolean
  onSelect: (keyword: string) => void
}

export function ReviewTopicChips({ topics, disabled = false, onSelect }: Props) {
  if (!topics.length) return null

  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#6B7378]">Mentioned in reviews</p>
      <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0">
        {topics.map((topic) => (
          <button
            key={topic.provider_topic_id}
            type="button"
            onClick={() => onSelect(topic.keyword)}
            disabled={disabled}
            className="min-h-11 shrink-0 rounded-full border border-[#DED8CE] bg-[#FFFDFC] px-4 py-2 text-sm text-[#24313A] hover:bg-[#F1ECE4] disabled:cursor-wait disabled:opacity-50"
          >
            {topic.keyword}{topic.mentions !== null && topic.mentions !== undefined ? ` (${topic.mentions})` : ''}
          </button>
        ))}
      </div>
    </div>
  )
}
