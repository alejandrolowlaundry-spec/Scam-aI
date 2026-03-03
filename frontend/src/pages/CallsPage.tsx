import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchCalls } from '../api/client'
import { CallTable } from '../components/CallTable'

const RISK_FILTERS = ['', 'high', 'medium', 'low'] as const
const FRAUD_FILTERS = ['', 'Confirmed Scam', 'Suspicious', 'Safe Customer'] as const

export function CallsPage() {
  const [riskLabel, setRiskLabel] = useState('')
  const [fraudLabel, setFraudLabel] = useState('')
  const [page, setPage] = useState(0)
  const limit = 25

  const { data, isLoading } = useQuery({
    queryKey: ['calls', riskLabel, fraudLabel, page],
    queryFn: () =>
      fetchCalls({
        risk_label: riskLabel || undefined,
        fraud_label: fraudLabel || undefined,
        limit,
        offset: page * limit,
      }),
  })

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">All Calls</h2>
        <span className="text-sm text-gray-500">{data?.total ?? 0} total</span>
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <select
          value={riskLabel}
          onChange={(e) => { setRiskLabel(e.target.value); setPage(0) }}
          className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All Risk Levels</option>
          <option value="high">High Risk</option>
          <option value="medium">Medium Risk</option>
          <option value="low">Low Risk</option>
        </select>

        <select
          value={fraudLabel}
          onChange={(e) => { setFraudLabel(e.target.value); setPage(0) }}
          className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All Verdicts</option>
          <option value="Confirmed Scam">Confirmed Scam</option>
          <option value="Suspicious">Suspicious</option>
          <option value="Safe Customer">Safe Customer</option>
        </select>

        {(riskLabel || fraudLabel) && (
          <button
            onClick={() => { setRiskLabel(''); setFraudLabel(''); setPage(0) }}
            className="text-sm text-gray-500 hover:text-gray-700 underline"
          >
            Clear filters
          </button>
        )}
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200">
        {isLoading ? (
          <div className="text-center py-16 text-gray-400">Loading…</div>
        ) : (
          <CallTable calls={data?.calls ?? []} />
        )}
      </div>

      {/* Pagination */}
      {data && data.total > limit && (
        <div className="flex justify-center gap-2">
          <button
            disabled={page === 0}
            onClick={() => setPage(p => p - 1)}
            className="px-4 py-2 text-sm border rounded-lg disabled:opacity-40 hover:bg-gray-50"
          >
            ← Previous
          </button>
          <span className="px-4 py-2 text-sm text-gray-500">
            Page {page + 1} of {Math.ceil(data.total / limit)}
          </span>
          <button
            disabled={(page + 1) * limit >= data.total}
            onClick={() => setPage(p => p + 1)}
            className="px-4 py-2 text-sm border rounded-lg disabled:opacity-40 hover:bg-gray-50"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  )
}
