import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  PieChart, Pie, Cell, ResponsiveContainer,
} from 'recharts'
import { fetchAnalytics } from '../api/client'
import { StatsCard } from '../components/StatsCard'

const PIE_COLORS = ['#10b981', '#f59e0b', '#ef4444']

export function Analytics() {
  const { data, isLoading } = useQuery({
    queryKey: ['analytics'],
    queryFn: fetchAnalytics,
    refetchInterval: 60_000,
  })

  if (isLoading || !data) {
    return <div className="text-center py-16 text-gray-400">Loading analytics…</div>
  }

  const pieData = [
    { name: 'Safe Customer', value: data.safe_customers },
    { name: 'Suspicious', value: data.suspicious },
    { name: 'Confirmed Scam', value: data.confirmed_scams },
  ].filter((d) => d.value > 0)

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Analytics</h2>
        <p className="text-sm text-gray-500 mt-1">Fraud verification performance overview</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatsCard label="Total Calls" value={data.total_calls} color="blue" />
        <StatsCard label="Confirmed Scams" value={data.confirmed_scams} color="red" />
        <StatsCard label="Suspicious" value={data.suspicious} color="yellow" />
        <StatsCard label="Avg Risk Score" value={data.avg_risk_score} sub="out of 100" color="default" />
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Calls by day */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
          <h3 className="font-semibold text-gray-800 mb-4">Calls by Day</h3>
          {data.calls_by_day.length === 0 ? (
            <p className="text-gray-400 text-sm text-center py-8">No data yet</p>
          ) : (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={data.calls_by_day} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="high" stackId="a" fill="#ef4444" name="High" />
                <Bar dataKey="medium" stackId="a" fill="#f59e0b" name="Medium" />
                <Bar dataKey="low" stackId="a" fill="#10b981" name="Low" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Verdict distribution */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
          <h3 className="font-semibold text-gray-800 mb-4">Verdict Distribution</h3>
          {pieData.length === 0 ? (
            <p className="text-gray-400 text-sm text-center py-8">No analyzed calls yet</p>
          ) : (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  dataKey="value"
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  labelLine={false}
                >
                  {pieData.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Top signals */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
        <h3 className="font-semibold text-gray-800 mb-4">Top Fraud Signals</h3>
        {data.top_signals.length === 0 ? (
          <p className="text-gray-400 text-sm">No signals detected yet</p>
        ) : (
          <div className="space-y-2">
            {data.top_signals.map(({ signal, count }) => (
              <div key={signal} className="flex items-center gap-3">
                <span className="w-36 text-sm text-gray-700 truncate">{signal}</span>
                <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-red-400 rounded-full"
                    style={{ width: `${(count / (data.top_signals[0]?.count || 1)) * 100}%` }}
                  />
                </div>
                <span className="text-sm font-semibold text-gray-600 w-8 text-right">{count}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
