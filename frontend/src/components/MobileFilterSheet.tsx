import { useEffect, useRef } from 'react'
import { ReviewFilters } from './ReviewFilters'
import type { ReviewFiltersProps } from '../types/ui'

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'textarea:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  '[tabindex]:not([tabindex="-1"])'
].join(',')

type Props = ReviewFiltersProps & {
  open: boolean
  onClose: () => void
}

export function MobileFilterSheet({ open, onClose, ...filterProps }: Props) {
  const sheetRef = useRef<HTMLDivElement | null>(null)
  const closeButtonRef = useRef<HTMLButtonElement | null>(null)

  useEffect(() => {
    if (!open) return
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    closeButtonRef.current?.focus()

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose()
        return
      }
      if (event.key !== 'Tab' || !sheetRef.current) return
      const focusable = Array.from(sheetRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
      if (!focusable.length) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', onKeyDown)
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-labelledby="mobile-filter-title">
      <button type="button" className="absolute inset-0 cursor-default bg-[#24313A]/35" aria-label="Close filters" onClick={onClose} />
      <div
        ref={sheetRef}
        className="absolute inset-x-0 bottom-0 max-h-[min(86dvh,720px)] overflow-y-auto rounded-t-3xl border border-[#DED8CE] bg-[#FFFDFC] px-4 pb-4 pt-3 shadow-2xl safe-pb"
      >
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 id="mobile-filter-title" className="text-lg font-semibold">Review filters</h2>
          <button ref={closeButtonRef} type="button" onClick={onClose} className="min-h-11 rounded-xl border border-[#CFC6BA] px-4 text-sm text-[#24313A]">
            Done
          </button>
        </div>
        <ReviewFilters {...filterProps} compact />
      </div>
    </div>
  )
}
