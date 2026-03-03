import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import axios from 'axios'

interface TestCallForm {
  phone: string
  email: string
  order_name: string
}

async function initiateTestCall(form: TestCallForm) {
  const { data } = await axios.post('/api/testing/call', form)
  return data
}

async function fetchTestCalls() {
  const { data } = await axios.get('/api/calls?limit=20')
  return data
}

export function TestingPage() {
  const [form, setForm] = useState<TestCallForm>({ phone: '', email: '', order_name: '' })
  const [result, setResult] = useState<any>(null)

  const mutation = useMutation({
    mutationFn: initiateTestCall,
    onSuccess: (data) => {
      setResult(data)
      setForm({ phone: '', email: '', order_name: '' })
    },
    onError: (err: any) => {
      alert(err?.response?.data?.detail || 'Failed to initiate test call')
    },
  })

  const { data: recentCalls, refetch } = useQuery({
    queryKey: ['test-calls'],
    queryFn: fetchTestCalls,
    refetchInterval: 10_000,
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.phone.trim()) return alert('Phone number is required')
    mutation.mutate(form)
  }

  return (
    <div className="max-w-3xl space-y-8">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Call Testing</h2>
        <p className="text-sm text-gray-500 mt-1">
          Trigger a test verification call to any number and see the full AI analysis pipeline live.
        </p>
      </div>

      {/* Form */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
        <h3 className="font-semibold text-gray-800 mb-5 flex items-center gap-2">
          <span className="w-7 h-7 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-sm font-bold">1</span>
          Enter Test Details
        </h3>

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Phone */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Phone Number <span className="text-red-500">*</span>
            </label>
            <div className="flex">
              <span className="inline-flex items-center px-3 rounded-l-lg border border-r-0 border-gray-300 bg-gray-50 text-gray-500 text-sm">
                📞
              </span>
              <input
                type="tel"
                placeholder="+1 555 000 0000"
                value={form.phone}
                onChange={e => setForm(f => ({ ...f, phone: e.target.value }))}
                className="flex-1 rounded-r-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>
            <p className="text-xs text-gray-400 mt-1">Use E.164 format: +15551234567</p>
          </div>

          {/* Email */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email (optional)</label>
            <div className="flex">
              <span className="inline-flex items-center px-3 rounded-l-lg border border-r-0 border-gray-300 bg-gray-50 text-gray-500 text-sm">
                ✉️
              </span>
              <input
                type="text"
                placeholder="you@example.com"
                value={form.email}
                onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                className="flex-1 rounded-r-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Order name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Order / Test Name (optional)</label>
            <div className="flex">
              <span className="inline-flex items-center px-3 rounded-l-lg border border-r-0 border-gray-300 bg-gray-50 text-gray-500 text-sm">
                📋
              </span>
              <input
                type="text"
                placeholder="e.g. Test Order #1234"
                value={form.order_name}
                onChange={e => setForm(f => ({ ...f, order_name: e.target.value }))}
                className="flex-1 rounded-r-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={mutation.isPending}
            className="w-full flex items-center justify-center gap-2 px-5 py-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-semibold rounded-lg transition-colors"
          >
            {mutation.isPending ? (
              <><span className="animate-spin">⏳</span> Initiating call…</>
            ) : (
              <><span>📞</span> Start Test Call</>
            )}
          </button>
        </form>
      </div>

      {/* Success result */}
      {result && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-5">
          <div className="flex items-start gap-3">
            <span className="text-2xl">✅</span>
            <div className="flex-1">
              <p className="font-semibold text-green-800">Call initiated successfully!</p>
              <div className="mt-2 text-sm text-green-700 space-y-1">
                <p><span className="font-medium">Call SID:</span> <span className="font-mono">{result.call_sid}</span></p>
                <p><span className="font-medium">Calling:</span> {result.phone_number}</p>
                <p><span className="font-medium">Status:</span> {result.message}</p>
              </div>
              <div className="mt-3 flex gap-3">
                <Link
                  to={`/calls/${result.call_sid}`}
                  className="text-sm text-blue-600 hover:text-blue-800 font-medium underline"
                >
                  View call analysis →
                </Link>
                <button
                  onClick={() => { setResult(null); refetch() }}
                  className="text-sm text-gray-500 hover:text-gray-700"
                >
                  Dismiss
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Pipeline explainer */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
        <h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
          <span className="w-7 h-7 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-sm font-bold">2</span>
          What happens after you call
        </h3>
        <ol className="space-y-3">
          {[
            { icon: '📞', label: 'Twilio dials your number', sub: 'You receive the call on your phone' },
            { icon: '🗣️', label: 'AI voice plays verification script', sub: 'ElevenLabs voice (or Twilio TTS if key not set)' },
            { icon: '🎙️', label: 'Call is recorded', sub: 'Recording stored securely via Twilio' },
            { icon: '📝', label: 'AssemblyAI transcribes the recording', sub: 'Full transcript generated in ~30 seconds' },
            { icon: '🤖', label: 'Claude analyzes the transcript', sub: 'Risk score 0–100 + fraud signals detected' },
            { icon: '📊', label: 'Results appear in the dashboard', sub: 'View the call detail page for full analysis' },
          ].map((step, i) => (
            <li key={i} className="flex items-start gap-3">
              <span className="text-xl w-7 text-center flex-shrink-0">{step.icon}</span>
              <div>
                <p className="text-sm font-medium text-gray-800">{step.label}</p>
                <p className="text-xs text-gray-400">{step.sub}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>

      {/* Recent test calls */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <h3 className="font-semibold text-gray-800 flex items-center gap-2">
            <span className="w-7 h-7 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-sm font-bold">3</span>
            Recent Calls
          </h3>
          <button onClick={() => refetch()} className="text-xs text-gray-400 hover:text-gray-600">
            Refresh
          </button>
        </div>

        {!recentCalls?.calls?.length ? (
          <div className="text-center py-10 text-gray-400 text-sm">No calls yet — trigger one above</div>
        ) : (
          <div className="divide-y divide-gray-50">
            {recentCalls.calls.map((call: any) => (
              <div key={call.call_sid} className="px-5 py-3 flex items-center justify-between hover:bg-gray-50">
                <div className="flex items-center gap-3">
                  <StatusDot status={call.status} />
                  <div>
                    <p className="text-sm font-medium text-gray-800">{call.to_number}</p>
                    <p className="text-xs text-gray-400 font-mono">{call.call_sid}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {call.risk_score !== null ? (
                    <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                      call.risk_label === 'high' ? 'bg-red-100 text-red-700' :
                      call.risk_label === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                      'bg-green-100 text-green-700'
                    }`}>
                      {call.risk_score}/100
                    </span>
                  ) : (
                    <span className="text-xs text-gray-400 italic">
                      {call.status === 'completed' ? 'Analyzing…' : call.status}
                    </span>
                  )}
                  <Link to={`/calls/${call.call_sid}`} className="text-xs text-blue-600 hover:text-blue-800">
                    View →
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function StatusDot({ status }: { status: string }) {
  const colors: Record<string, string> = {
    completed: 'bg-green-400',
    'in-progress': 'bg-blue-400 animate-pulse',
    initiated: 'bg-yellow-400 animate-pulse',
    ringing: 'bg-yellow-400 animate-pulse',
    failed: 'bg-red-400',
  }
  return (
    <span className={`w-2 h-2 rounded-full flex-shrink-0 ${colors[status] ?? 'bg-gray-300'}`} />
  )
}
