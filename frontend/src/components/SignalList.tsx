import type { FraudSignals } from '../types'

export function SignalList({ signals }: { signals: FraudSignals }) {
  const items = [
    { label: 'Keywords', values: signals.keywords, color: 'red' },
    { label: 'Pressure Tactics', values: signals.pressure_tactics, color: 'orange' },
    { label: 'Script Matches', values: signals.script_match, color: 'purple' },
    { label: 'Inconsistencies', values: signals.inconsistencies, color: 'yellow' },
  ] as const

  const colorMap = {
    red: 'bg-red-100 text-red-700',
    orange: 'bg-orange-100 text-orange-700',
    purple: 'bg-purple-100 text-purple-700',
    yellow: 'bg-yellow-100 text-yellow-700',
  }

  return (
    <div className="space-y-3">
      {signals.spoofing_suspected && (
        <div className="flex items-center gap-2 p-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          <span>⚠️</span> Spoofed caller ID suspected
        </div>
      )}
      {items.map(({ label, values, color }) =>
        values.length > 0 ? (
          <div key={label}>
            <p className="text-xs font-semibold text-gray-500 uppercase mb-1">{label}</p>
            <div className="flex flex-wrap gap-1.5">
              {values.map((v) => (
                <span key={v} className={`text-xs px-2 py-0.5 rounded-full font-medium ${colorMap[color]}`}>
                  {v}
                </span>
              ))}
            </div>
          </div>
        ) : null
      )}
      {!signals.spoofing_suspected &&
        items.every((i) => i.values.length === 0) && (
          <p className="text-sm text-gray-400 italic">No fraud signals detected</p>
        )}
    </div>
  )
}
