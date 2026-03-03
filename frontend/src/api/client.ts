import axios from 'axios'
import type { Call, CallListResponse, HubSpotDeal, AnalyticsSummary } from '../types'

const api = axios.create({ baseURL: '/api' })

// ── Calls ──────────────────────────────────────────────────────────────────────

export async function fetchCalls(params?: {
  risk_label?: string
  fraud_label?: string
  limit?: number
  offset?: number
}): Promise<CallListResponse> {
  const { data } = await api.get('/calls', { params })
  return data
}

export async function fetchCall(callSid: string): Promise<Call> {
  const { data } = await api.get(`/calls/${callSid}`)
  return data
}

// ── HubSpot ────────────────────────────────────────────────────────────────────

export async function fetchPendingDeals(): Promise<{ total: number; deals: HubSpotDeal[] }> {
  const { data } = await api.get('/hubspot/deals')
  return data
}

export async function initiateCall(dealId: string) {
  const { data } = await api.post(`/hubspot/initiate-call/${dealId}`)
  return data
}

// ── Analytics ──────────────────────────────────────────────────────────────────

export async function fetchAnalytics(): Promise<AnalyticsSummary> {
  const { data } = await api.get('/analytics/summary')
  return data
}
