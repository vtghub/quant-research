export interface User {
  id: number
  email: string
  created_at: string
}

export interface SavedConfig {
  id: number
  name: string
  config_json: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface EquityPoint {
  date: string
  value: number | null
}

export interface ICSummary {
  mean_ic: number
  std_ic: number
  ic_ir: number
  t_stat: number
  hit_rate: number
}

export interface RunResult {
  signals?: Record<string, string[]>
  price_symbols?: string[]
  date_range?: [string, string] | null
  ic_summary?: Record<string, ICSummary>
  metrics?: Record<string, number | null>
  equity_curve?: EquityPoint[]
  report_paths?: string[]
}

export interface Run {
  id: number
  kind: 'research' | 'backtest'
  status: 'pending' | 'running' | 'success' | 'failed'
  config_id: number | null
  error_message: string | null
  result_json: RunResult | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface Registry {
  data_sources: string[]
  macro_sources: string[]
  fundamentals_sources: string[]
  cache_backends: string[]
  universe_providers: string[]
  signals: string[]
  strategies: string[]
}
