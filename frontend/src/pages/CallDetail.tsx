import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'
import { fetchCall } from '../api/client'
import { RiskBadge, FraudBadge, ScoreBar } from '../components/RiskBadge'
import { SignalList } from '../components/SignalList'

export function CallDetail() {
  const { callSid } = useParams<{ callSid: string }>()
  const { data: call, isLoading, error } = useQuery({
    queryKey: ['call', callSid],
    queryFn: () => fetchCall(callSid!),
  })

  if (isLoading) return <div className="text-center py-16 text-gray-400">Loading call…</div>
  if (error || !call) return <div className="text-center py-16 text-red-500">Call not found</div>

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center gap-3">
        <Link to="/calls" className="text-blue-600 hover:text-blue-800 text-sm">← All Calls</Link>
        <span className="text-gray-300">/</span>
        <span className="text-sm font-mono text-gray-500">{call.call_sid}</span>
      </div>

      {/* Header */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <FraudBadge label={call.fraud_label} />
              <RiskBadge label={call.risk_label} />
              {call.alert_sent && (
                <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full">🔔 Alert sent</span>
              )}
              {call.hubspot_updated && (
                <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">↗ HubSpot updated</span>
              )}
            </div>
            <p className="text-gray-600 text-sm mt-1">{call.analysis_summary || 'Analysis in progress…'}</p>
          </div>
          <div className="text-right">
            <ScoreBar score={call.risk_score} />
            <p className="text-xs text-gray-400 mt-1">risk score</p>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-5 pt-5 border-t border-gray-100">
          <Pair label="From" value={call.from_number} />
          <Pair label="To" value={call.to_number} />
          <Pair label="Direction" value={call.direction} />
          <Pair label="Duration" value={call.duration ? `${call.duration}s` : '—'} />
          <Pair label="Status" value={call.status} />
          <Pair label="Time" value={format(new Date(call.created_at), 'MMM d yyyy, HH:mm')} />
          {call.hubspot_deal_id && <Pair label="HubSpot Deal" value={call.hubspot_deal_id} />}
        </div>
      </div>

      {/* Reasons */}
      {call.reasons && call.reasons.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
          <h3 className="font-semibold text-gray-800 mb-3">Analysis Reasons</h3>
          <ul className="space-y-2">
            {call.reasons.map((r, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                <span className="text-gray-400 mt-0.5">•</span>
                {r}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Signals */}
      {call.signals && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
          <h3 className="font-semibold text-gray-800 mb-3">Detected Signals</h3>
          <SignalList signals={call.signals} />
        </div>
      )}

      {/* Transcript */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
        <h3 className="font-semibold text-gray-800 mb-3">Transcript</h3>
        {call.transcript ? (
          <pre className="text-sm text-gray-700 whitespace-pre-wrap font-sans leading-relaxed bg-gray-50 rounded-lg p-4 max-h-96 overflow-y-auto">
            {call.transcript}
          </pre>
        ) : (
          <p className="text-sm text-gray-400 italic">Transcript not yet available</p>
        )}
        {call.recording_url && (
          <a
            href={call.recording_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 mt-3 text-sm text-blue-600 hover:text-blue-800"
          >
            🎧 Play Recording
          </a>
        )}
      </div>

      {/* Raw Claude JSON (debug) */}
      {call.raw_claude_json && (
        <details className="bg-gray-50 rounded-xl border border-gray-200 p-4">
          <summary className="cursor-pointer text-sm font-medium text-gray-600">Raw Claude JSON (debug)</summary>
          <pre className="mt-3 text-xs text-gray-600 overflow-auto max-h-64">
            {JSON.stringify(call.raw_claude_json, null, 2)}
          </pre>
        </details>
      )}
    </div>
  )
}

function Pair({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-gray-400 uppercase font-medium">{label}</p>
      <p className="text-sm font-medium text-gray-800 mt-0.5">{value}</p>
    </div>
  )
}
