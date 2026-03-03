export type RiskLabel = 'low' | 'medium' | 'high'
export type FraudLabel = 'Safe Customer' | 'Suspicious' | 'Confirmed Scam'

export interface FraudSignals {
  keywords: string[]
  pressure_tactics: string[]
  spoofing_suspected: boolean
  inconsistencies: string[]
  script_match: string[]
}

export interface Call {
  id: number
  call_sid: string
  hubspot_deal_id: string | null
  from_number: string
  to_number: string
  direction: string
  duration: number | null
  status: string
  recording_url: string | null
  transcript: string | null
  risk_score: number | null
  risk_label: RiskLabel | null
  fraud_label: FraudLabel | null
  reasons: string[] | null
  signals: FraudSignals | null
  analysis_summary: string | null
  raw_claude_json: Record<string, unknown> | null
  hubspot_updated: boolean
  alert_sent: boolean
  created_at: string
  updated_at: string
}

export interface CallListResponse {
  total: number
  calls: Call[]
}

export interface HubSpotDeal {
  deal_id: string
  deal_name: string
  fraud_status: string
  contact_phone: string | null
  contact_name: string | null
  contact_email: string | null
  contact_id: string | null
  amount: string | null
  created_at: string | null
}

export interface DailyCount {
  date: string
  total: number
  high: number
  medium: number
  low: number
}

export interface TopSignal {
  signal: string
  count: number
}

export interface AnalyticsSummary {
  total_calls: number
  safe_customers: number
  suspicious: number
  confirmed_scams: number
  avg_risk_score: number
  calls_by_day: DailyCount[]
  top_signals: TopSignal[]
}
