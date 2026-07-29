import { RestaurantReviewPane } from './RestaurantReviewPane'
import { SearchPane } from './SearchPane'
import type { WorkspaceProps } from '../types/ui'

export function Workspace(props: WorkspaceProps) {
  return (
    <section className="h-[calc(100vh-3.5rem)] lg:grid lg:grid-cols-[400px_minmax(0,1fr)]">
      <aside className={`${props.mobilePane === 'reviews' ? 'hidden' : 'block'} h-full overflow-y-auto border-r border-[#DED8CE] lg:block`}>
        <SearchPane {...props} />
      </aside>
      <section className={`${props.mobilePane === 'results' ? 'hidden' : 'block'} h-full min-w-0 overflow-y-auto lg:block`}>
        <RestaurantReviewPane {...props} />
      </section>
    </section>
  )
}
