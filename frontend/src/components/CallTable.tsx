import { Link } from 'react-router-dom'
import { format } from 'date-fns'
import { RiskBadge, FraudBadge, ScoreBar } from './RiskBadge'
import type { Call } from '../types'

export function CallTable({ calls }: { calls: Call[] }) {
  if (!calls.length) {
    return (
      <div className="text-center py-16 text-gray-400">
        <p className="text-lg">No calls found</p>
        <p className="text-sm mt-1">Initiate a call from the HubSpot Deals page to get started.</p>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            {['Time', 'From', 'To', 'Deal', 'Score', 'Risk', 'Verdict', 'Status', ''].map((h) => (
              <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-100">
          {calls.map((call) => (
            <tr key={call.call_sid} className="hover:bg-gray-50 transition-colors">
              <td className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">
                {format(new Date(call.created_at), 'MMM d, HH:mm')}
              </td>
              <td className="px-4 py-3 text-sm font-mono text-gray-700">{call.from_number}</td>
              <td className="px-4 py-3 text-sm font-mono text-gray-700">{call.to_number}</td>
              <td className="px-4 py-3 text-sm text-gray-500">
                {call.hubspot_deal_id ? (
                  <span className="text-blue-600 text-xs font-mono">{call.hubspot_deal_id}</span>
                ) : (
                  <span className="text-gray-300">—</span>
                )}
              </td>
              <td className="px-4 py-3">
                <ScoreBar score={call.risk_score} />
              </td>
              <td className="px-4 py-3">
                <RiskBadge label={call.risk_label} />
              </td>
              <td className="px-4 py-3">
                <FraudBadge label={call.fraud_label} />
              </td>
              <td className="px-4 py-3">
                <span className="text-xs text-gray-500 capitalize">{call.status}</span>
                {call.hubspot_updated && (
                  <span className="ml-1 text-xs text-blue-500" title="HubSpot updated">↗</span>
                )}
              </td>
              <td className="px-4 py-3 text-right">
                <Link
                  to={`/calls/${call.call_sid}`}
                  className="text-xs text-blue-600 hover:text-blue-800 font-medium"
                >
                  View →
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
