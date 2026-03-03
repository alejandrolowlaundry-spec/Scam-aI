import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchCalls, fetchAnalytics } from '../api/client'
import { StatsCard } from '../components/StatsCard'
import { CallTable } from '../components/CallTable'

export function Dashboard() {
  const { data: callsData } = useQuery({
    queryKey: ['calls', 'recent'],
    queryFn: () => fetchCalls({ limit: 10 }),
    refetchInterval: 15_000,
  })

  const { data: analytics } = useQuery({
    queryKey: ['analytics'],
    queryFn: fetchAnalytics,
    refetchInterval: 30_000,
  })

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>
        <p className="text-sm text-gray-500 mt-1">Real-time fraud verification overview</p>
      </div>

      {analytics && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatsCard
            label="Total Calls"
            value={analytics.total_calls}
            color="blue"
          />
          <StatsCard
            label="Confirmed Scams"
            value={analytics.confirmed_scams}
            sub={`${analytics.total_calls ? Math.round((analytics.confirmed_scams / analytics.total_calls) * 100) : 0}% of total`}
            color="red"
          />
          <StatsCard
            label="Suspicious"
            value={analytics.suspicious}
            color="yellow"
          />
          <StatsCard
            label="Safe Customers"
            value={analytics.safe_customers}
            color="green"
          />
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm border border-gray-200">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <h3 className="font-semibold text-gray-800">Recent Calls</h3>
          <Link to="/calls?risk_label=high" className="text-sm text-red-600 hover:text-red-800 font-medium">
            View high-risk only →
          </Link>
        </div>
        <CallTable calls={callsData?.calls ?? []} />
      </div>
    </div>
  )
}
