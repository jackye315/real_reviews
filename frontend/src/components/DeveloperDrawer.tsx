import { useEffect, useRef } from 'react'
import { ProviderUsagePanel } from './ProviderUsagePanel'
import type { DeveloperDrawerProps } from '../types/ui'

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'textarea:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  '[tabindex]:not([tabindex="-1"])'
].join(',')

export function DeveloperDrawer({ open, usage, loading, onRefresh, onClose }: DeveloperDrawerProps) {
  const drawerRef = useRef<HTMLElement | null>(null)
  const closeButtonRef = useRef<HTMLButtonElement | null>(null)

  useEffect(() => {
    if (!open) return
    closeButtonRef.current?.focus()
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose()
        return
      }
      if (event.key !== 'Tab' || !drawerRef.current) return
      const focusable = Array.from(drawerRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
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
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-labelledby="developer-drawer-title">
      <button className="absolute inset-0 cursor-default bg-[#24313A]/35 motion-safe:transition-opacity" aria-label="Close developer drawer" onClick={onClose} />
      <aside ref={drawerRef} className="absolute bottom-0 right-0 top-auto max-h-[min(82dvh,720px)] w-full overflow-y-auto rounded-t-3xl border border-[#DED8CE] bg-[#FFFDFC] p-5 shadow-2xl motion-safe:transition-transform safe-pb sm:top-0 sm:h-full sm:max-h-none sm:max-w-md sm:rounded-none sm:border-l">
        <div className="flex items-center justify-between gap-3">
          <h2 id="developer-drawer-title" className="text-lg font-semibold">Provider usage</h2>
          <button ref={closeButtonRef} onClick={onClose} className="min-h-11 rounded-lg border border-[#CFC6BA] px-3 py-1 text-sm text-[#24313A]">Close</button>
        </div>
        <div className="mt-4 flex justify-end">
          <button onClick={onRefresh} className="min-h-11 text-sm text-[#35647C] hover:underline">Refresh usage</button>
        </div>
        <ProviderUsagePanel usage={usage} loading={loading} />
      </aside>
    </div>
  )
}
