export interface Selection {
  exchange: string
  symbol: string
  market: 'spot' | 'swap'
  timeframe: string
  limit: number
}
export interface Candle { time: number; open: number; high: number; low: number; close: number; volume: number }
export interface Report {
  metadata: {
    source: string; exchange: string; symbol: string; market: string; timeframe: string
    last_candle_at: string; fetched_at: string; bars: number; quote: string; warnings: string[]
    derivatives?: {
      funding: { status: string; fundingRate?: number | null; fundingTimestamp?: number | null; interval?: string | null }
      open_interest: { status: string; openInterestAmount?: number | null; openInterestValue?: number | null; timestamp?: number | null }
    }
  }
  latest_close: number; change_pct: number; ma20: number; ma50: number; ma200: number | null
  atr14: number | null; signals: string[]; stage: string; note: string; summary: string
  trading_range: { support: number; resistance: number; quality_score: number } | null
  candles: Candle[]
}
export interface ChatMessage { role: 'user' | 'assistant'; content: string }
export interface HistoryItem { id: number; created_at: string; report: Report }
export interface Config { llm_enabled: boolean; exchanges: string[]; timeframes: string[] }

export async function api<T>(path: string, token: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { Authorization: `Bearer ${token}`, ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(600_000),
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: unknown } | null
    throw new Error(typeof payload?.detail === 'string' ? payload.detail : `请求失败 (${response.status})`)
  }
  return response.json() as Promise<T>
}

export function number(value: number | null | undefined): string {
  return value == null ? '—' : value.toLocaleString('en-US', { maximumSignificantDigits: 8 })
}
