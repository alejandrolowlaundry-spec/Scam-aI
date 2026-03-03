import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchPendingDeals, initiateCall } from '../api/client'
import type { HubSpotDeal } from '../types'

export function HubSpotDeals() {
  const qc = useQueryClient()
  const [callingDealId, setCallingDealId] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['hubspot-deals'],
    queryFn: fetchPendingDeals,
    refetchInterval: 60_000,
  })

  const callMutation = useMutation({
    mutationFn: (dealId: string) => initiateCall(dealId),
    onSuccess: (result, dealId) => {
      setCallingDealId(null)
      setSuccessMsg(`Call initiated to ${result.phone_number} (SID: ${result.call_sid})`)
      qc.invalidateQueries({ queryKey: ['calls'] })
      setTimeout(() => setSuccessMsg(null), 6000)
    },
    onError: (err: any) => {
      setCallingDealId(null)
      alert(err?.response?.data?.detail || 'Failed to initiate call')
    },
  })

  const handleCall = (deal: HubSpotDeal) => {
    if (!deal.contact_phone) return alert('No phone number on this contact')
    if (!confirm(`Call ${deal.contact_name ?? deal.contact_phone}?`)) return
    setCallingDealId(deal.deal_id)
    callMutation.mutate(deal.deal_id)
  }

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">HubSpot Deals</h2>
        <p className="text-sm text-gray-500 mt-1">
          Deals pending fraud verification · {data?.total ?? 0} found
        </p>
      </div>

      {successMsg && (
        <div className="bg-green-50 border border-green-200 text-green-800 text-sm px-4 py-3 rounded-lg">
          ✅ {successMsg}
        </div>
      )}

      {isLoading ? (
        <div className="text-center py-16 text-gray-400">Loading HubSpot deals…</div>
      ) : !data?.deals.length ? (
        <div className="text-center py-16 bg-white rounded-xl border border-gray-200">
          <p className="text-gray-400">No deals pending verification</p>
          <p className="text-xs text-gray-300 mt-1">
            Set fraud_verification_status = "Pending Verification for Fraud" in HubSpot to populate this list
          </p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {data.deals.map((deal) => (
            <DealCard
              key={deal.deal_id}
              deal={deal}
              isCalling={callingDealId === deal.deal_id}
              onCall={() => handleCall(deal)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function DealCard({
  deal,
  isCalling,
  onCall,
}: {
  deal: HubSpotDeal
  isCalling: boolean
  onCall: () => void
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 flex flex-col gap-4">
      <div>
        <p className="font-semibold text-gray-900">{deal.deal_name}</p>
        <p className="text-xs text-gray-400 font-mono mt-0.5">{deal.deal_id}</p>
      </div>

      <div className="text-sm space-y-1 text-gray-600">
        {deal.contact_name && <p>👤 {deal.contact_name}</p>}
        {deal.contact_phone && <p>📞 <span className="font-mono">{deal.contact_phone}</span></p>}
        {deal.contact_email && <p>✉️ {deal.contact_email}</p>}
        {deal.amount && <p>💰 ${Number(deal.amount).toLocaleString()}</p>}
      </div>

      <div className="flex items-center justify-between pt-2 border-t border-gray-100">
        <span className="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded-full font-medium">
          {deal.fraud_status}
        </span>
        <button
          onClick={onCall}
          disabled={isCalling || !deal.contact_phone}
          className="flex items-center gap-1.5 px-4 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
        >
          {isCalling ? (
            <><span className="animate-spin">⏳</span> Calling…</>
          ) : (
            <><span>📞</span> Verify Now</>
          )}
        </button>
      </div>
    </div>
  )
}
