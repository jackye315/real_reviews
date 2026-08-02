import type { ProviderOperation } from '../types/api'

type Props = {
  operations: ProviderOperation[]
  loading: boolean
}

export function ProviderOperationsPanel({ operations, loading }: Props) {
  return (
    <section className="mt-6 border-t border-[#DED8CE] pt-5">
      <h3 className="text-sm font-semibold uppercase tracking-[0.12em] text-[#4B5A63]">Recent provider operations</h3>
      {loading ? <p className="mt-3 text-sm text-[#6B7378]">Loading operations…</p> : null}
      {!loading && !operations.length ? <p className="mt-3 text-sm text-[#6B7378]">No provider operations yet.</p> : null}
      <ul className="mt-3 space-y-3">
        {operations.map((operation) => (
          <li key={operation.operation_id} className="rounded-xl border border-[#DED8CE] p-3 text-sm text-[#4B5A63]">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-medium text-[#24313A]">{operation.operation_type} · {operation.restaurant_name ?? 'Unknown restaurant'}</span>
              <span className="rounded-full bg-[#F1ECE4] px-2 py-0.5 text-xs">{operation.status}</span>
            </div>
            <p className="mt-1 text-xs text-[#6B7378]">{operation.operation_id.slice(0, 8)} · {new Date(operation.updated_at).toLocaleString()}</p>
            <p className="mt-2">Estimated/reserved: {operation.estimated_request_count}/{operation.reserved_request_count} · successful {operation.successful_request_count} · cached {operation.cached_response_count} · failed {operation.failed_request_count} · uncertain {operation.uncertain_request_count} · released {operation.released_reserved_count}</p>
            {operation.stop_reason ? <p className="mt-1 text-xs text-[#6B7378]">Stop: {operation.stop_reason}</p> : null}
          </li>
        ))}
      </ul>
    </section>
  )
}
