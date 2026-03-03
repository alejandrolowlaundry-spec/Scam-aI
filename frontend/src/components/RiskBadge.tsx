import clsx from 'clsx'
import type { RiskLabel, FraudLabel } from '../types'

const riskColors: Record<RiskLabel, string> = {
  high: 'bg-red-100 text-red-800 border border-red-200',
  medium: 'bg-yellow-100 text-yellow-800 border border-yellow-200',
  low: 'bg-green-100 text-green-800 border border-green-200',
}

const fraudColors: Record<FraudLabel, string> = {
  'Confirmed Scam': 'bg-red-100 text-red-800 border border-red-200',
  'Suspicious': 'bg-yellow-100 text-yellow-800 border border-yellow-200',
  'Safe Customer': 'bg-green-100 text-green-800 border border-green-200',
}

export function RiskBadge({ label }: { label: RiskLabel | null }) {
  if (!label) return <span className="text-gray-400 text-xs">Pending</span>
  return (
    <span className={clsx('px-2 py-0.5 rounded-full text-xs font-semibold uppercase', riskColors[label])}>
      {label}
    </span>
  )
}

export function FraudBadge({ label }: { label: FraudLabel | null }) {
  if (!label) return <span className="text-gray-400 text-xs">Analyzing…</span>
  return (
    <span className={clsx('px-2.5 py-1 rounded-full text-xs font-semibold', fraudColors[label])}>
      {label}
    </span>
  )
}

export function ScoreBar({ score }: { score: number | null }) {
  if (score === null) return <span className="text-gray-400 text-xs">—</span>
  const color = score >= 70 ? 'bg-red-500' : score >= 40 ? 'bg-yellow-400' : 'bg-green-500'
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-2 bg-gray-200 rounded-full overflow-hidden">
        <div className={clsx('h-full rounded-full', color)} style={{ width: `${score}%` }} />
      </div>
      <span className="text-sm font-mono font-semibold">{score}</span>
    </div>
  )
}
