import clsx from 'clsx'

interface Props {
  label: string
  value: string | number
  sub?: string
  color?: 'red' | 'yellow' | 'green' | 'blue' | 'default'
}

const colorMap = {
  red: 'border-l-red-500 bg-red-50',
  yellow: 'border-l-yellow-400 bg-yellow-50',
  green: 'border-l-green-500 bg-green-50',
  blue: 'border-l-blue-500 bg-blue-50',
  default: 'border-l-gray-300 bg-white',
}

export function StatsCard({ label, value, sub, color = 'default' }: Props) {
  return (
    <div className={clsx('rounded-lg border-l-4 p-5 shadow-sm', colorMap[color])}>
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</p>
      <p className="mt-1 text-3xl font-bold text-gray-900">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-gray-500">{sub}</p>}
    </div>
  )
}
