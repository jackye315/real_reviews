import type { ProviderUsage } from '../types/api'

export function ProviderUsagePanel({ usage, loading }: { usage: ProviderUsage[]; loading: boolean }) {
  if (loading) return <p className="mt-6 text-sm text-[#6B7378]">Loading provider usage…</p>
  if (!usage.length) return <p className="mt-6 text-sm text-[#7B746C]">No tracked usage yet.</p>
  return (
    <table className="mt-6 w-full text-left text-sm">
      <thead className="text-[#6B7378]">
        <tr className="border-b border-[#DED8CE]">
          <th className="py-2 font-medium">Provider</th>
          <th className="py-2 font-medium">Period</th>
          <th className="py-2 font-medium">Success</th>
          <th className="py-2 font-medium">Failed</th>
        </tr>
      </thead>
      <tbody>
        {usage.map((item) => (
          <tr key={item.id} className="border-b border-[#EEE7DD]">
            <td className="py-2">{item.provider}</td>
            <td className="py-2 text-[#6B7378]">{item.plan_period}</td>
            <td className="py-2 text-[#4B5A63]">{item.successful_request_count}</td>
            <td className="py-2 text-[#4B5A63]">{item.failed_request_count}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
