import { useState } from 'react'
import type { ReviewDetailValue, ReviewImage } from '../types/api'

type DetailMap = Record<string, ReviewDetailValue>

const labels: Record<string, string> = {
  order_type: 'Order type',
  service_type: 'Service type',
  order_service_type: 'Order / service type',
  meal_type: 'Meal type',
  price_per_person: 'Price per person',
  price: 'Price',
  food: 'Food',
  service: 'Service',
  atmosphere: 'Atmosphere',
  recommended_dishes: 'Recommended dishes',
  dietary_options: 'Dietary options',
  parking: 'Parking',
  accessibility: 'Accessibility',
  seating: 'Seating'
}

const recognizedOrder = [
  'order_service_type', 'order_type', 'service_type', 'meal_type', 'price_per_person', 'price',
  'food', 'service', 'atmosphere', 'recommended_dishes', 'dietary_options', 'parking', 'accessibility', 'seating'
]
const fullWidthKeys = new Set(['recommended_dishes', 'dietary_options', 'parking', 'accessibility', 'seating'])

function normalizedKey(key: string) {
  return key.normalize('NFKC').trim().toLowerCase().replace(/[\s-]+/g, '_').replace(/_+/g, '_')
}

function compatible(original: ReviewDetailValue, translated: ReviewDetailValue | undefined) {
  if (translated === undefined) return false
  if (Array.isArray(original) !== Array.isArray(translated)) return false
  if (Array.isArray(original) && Array.isArray(translated)) return translated.length > 0
  return !(typeof translated === 'string' && translated.length === 0)
}

function valueText(value: ReviewDetailValue) {
  return Array.isArray(value) ? value.join(', ') : String(value)
}

function genericLabel(key: string) {
  return key.replace(/[_-]+/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function DetailRows({ details, translatedDetails }: { details: DetailMap; translatedDetails: DetailMap }) {
  const entries = Object.entries(details).map(([key, value]) => ({ key, normalized: normalizedKey(key), value }))
  const translatedByKey = new Map<string, ReviewDetailValue>()
  for (const [key, value] of Object.entries(translatedDetails)) {
    const normalized = normalizedKey(key)
    if (!translatedByKey.has(normalized)) translatedByKey.set(normalized, value)
  }
  const position = (entry: { normalized: string }) => {
    const index = recognizedOrder.indexOf(entry.normalized)
    return index === -1 ? [1, entry.normalized] : [0, String(index).padStart(2, '0')]
  }
  entries.sort((a, b) => position(a).join(':').localeCompare(position(b).join(':')))
  if (!entries.length) return null
  return (
    <dl aria-label="Review details" className="mt-2 grid grid-cols-1 gap-x-4 gap-y-2 rounded-xl bg-[#F7F4EE] p-3.5 text-sm min-[360px]:grid-cols-2 lg:grid-cols-3">
      {entries.map((entry) => {
        const translated = translatedByKey.get(entry.normalized)
        const display = compatible(entry.value, translated) ? translated! : entry.value
        const fullWidth = fullWidthKeys.has(entry.normalized) || Array.isArray(display) || valueText(display).length > 48
        return (
          <div key={entry.key} className={`min-w-0 ${fullWidth ? 'min-[360px]:col-span-2 lg:col-span-3' : ''}`}>
            <dt className="text-xs font-semibold uppercase tracking-wide text-[#4E5A61]">{labels[entry.normalized] ?? genericLabel(entry.key)}</dt>
            <dd className="mt-0.5 break-words text-[#24313A]">{valueText(display)}</dd>
          </div>
        )
      })}
    </dl>
  )
}

function ReviewImageGallery({ images }: { images: ReviewImage[] }) {
  const [broken, setBroken] = useState<Set<string>>(new Set())
  const visible = images.filter((image) => !broken.has(image.url))
  if (!visible.length) return null
  return (
    <section className="mt-2 min-w-0" aria-label="Review photos">
      <div data-testid="review-photo-strip" className="flex w-full max-w-full snap-x gap-2 overflow-x-auto pb-1">
        {visible.map((image, index) => (
          <img
            key={`${image.url}-${image.position}`}
            className="h-28 w-36 shrink-0 snap-start rounded-lg border border-[#DED8CE] object-cover"
            src={image.url}
            alt={`Review photo ${index + 1}`}
            loading="lazy"
            decoding="async"
            referrerPolicy="no-referrer"
            onError={() => setBroken((current) => new Set(current).add(image.url))}
          />
        ))}
      </div>
      <p className="mt-1 text-xs text-[#6B7378]">Review photos supplied by Google via SerpApi.</p>
    </section>
  )
}

export function ReviewRichData({ details, translatedDetails, images }: { details: DetailMap; translatedDetails: DetailMap; images: ReviewImage[] }) {
  return <><DetailRows details={details} translatedDetails={translatedDetails} /><ReviewImageGallery images={images} /></>
}
