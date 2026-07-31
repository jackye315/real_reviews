import { RestaurantReviewPane } from './RestaurantReviewPane'
import { SearchPane } from './SearchPane'
import type { WorkspaceProps } from '../types/ui'

export function Workspace(props: WorkspaceProps) {
  return (
    <section className="workspace-height min-h-0 overflow-hidden lg:grid lg:grid-cols-[400px_minmax(0,1fr)]">
      <aside className={`${props.mobilePane === 'reviews' ? 'hidden' : 'block'} h-full min-h-0 overflow-y-auto overscroll-contain border-r border-[#DED8CE] lg:block`}>
        <SearchPane {...props} />
      </aside>
      <section className={`${props.mobilePane === 'results' ? 'hidden' : 'block'} h-full min-h-0 min-w-0 overflow-y-auto overscroll-contain lg:block`}>
        <RestaurantReviewPane {...props} />
      </section>
    </section>
  )
}
