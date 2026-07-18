import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { Registry, SavedConfig } from '../types'

const TEMPLATE = {
  name: 'my_pipeline',
  universe: {
    symbols: ['SPY', 'QQQ', 'TLT'],
    asset_class: 'etf',
    start: '2020-01-01',
    end: '2024-01-01',
    primary_source: 'yfinance',
  },
  signals: [{ name: 'momentum', alias: 'mom', params: { lookback: 126, skip_recent: 21 } }],
  ic_analysis: { enabled: true, horizons: [1, 5, 21, 63], n_quantiles: 5 },
  strategy: { name: 'rank_weighted_long_short', signals: ['mom'], params: { top_frac: 0.3, bottom_frac: 0.3 } },
  backtest: { initial_capital: 1000000, cost_model: { name: 'bps', bps_per_trade: 5.0 }, rebalance: 'weekly' },
}

export function ConfigBuilderPage() {
  const { configId } = useParams<{ configId: string }>()
  const isNew = !configId || configId === 'new'
  const navigate = useNavigate()

  const [name, setName] = useState('my_pipeline')
  const [configText, setConfigText] = useState(JSON.stringify(TEMPLATE, null, 2))
  const [registry, setRegistry] = useState<Registry | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.get<Registry>('/registry').then(setRegistry).catch(() => undefined)
  }, [])

  useEffect(() => {
    if (isNew) return
    api.get<SavedConfig>(`/configs/${configId}`).then((config) => {
      setName(config.name)
      setConfigText(JSON.stringify(config.config_json, null, 2))
    })
  }, [configId, isNew])

  function parseConfig(): Record<string, unknown> | null {
    try {
      return JSON.parse(configText)
    } catch {
      setError('config_json is not valid JSON')
      return null
    }
  }

  async function handleSave() {
    const config_json = parseConfig()
    if (!config_json) return
    setError(null)
    setSaving(true)
    try {
      if (isNew) {
        await api.post('/configs', { name, config_json })
      } else {
        await api.put(`/configs/${configId}`, { name, config_json })
      }
      navigate('/')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to save config')
    } finally {
      setSaving(false)
    }
  }

  async function handleSaveAndRun(kind: 'research' | 'backtest') {
    const config_json = parseConfig()
    if (!config_json) return
    setError(null)
    setSaving(true)
    try {
      const saved = isNew
        ? await api.post<SavedConfig>('/configs', { name, config_json })
        : await api.put<SavedConfig>(`/configs/${configId}`, { name, config_json })
      const run = await api.post<{ id: number }>('/runs', { config_id: saved.id, kind })
      navigate(`/runs/${run.id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to save/run config')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="page">
      <header className="topbar">
        <h1>{isNew ? 'New config' : 'Edit config'}</h1>
        <Link to="/">
          <button>Back to dashboard</button>
        </Link>
      </header>

      <div className="builder-layout">
        <div className="card builder-main">
          <label>
            Name
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <label>
            config_json
            <textarea
              value={configText}
              onChange={(e) => setConfigText(e.target.value)}
              rows={24}
              spellCheck={false}
              className="code"
            />
          </label>
          {error && <pre className="error">{error}</pre>}
          <div className="row-actions">
            <button onClick={handleSave} disabled={saving}>
              Save
            </button>
            <button onClick={() => handleSaveAndRun('research')} disabled={saving}>
              Save &amp; run research
            </button>
            <button onClick={() => handleSaveAndRun('backtest')} disabled={saving}>
              Save &amp; run backtest
            </button>
          </div>
        </div>

        <aside className="card builder-sidebar">
          <h3>Registry reference</h3>
          {!registry ? (
            <p className="muted">Loading…</p>
          ) : (
            <>
              <RegistrySection title="Data sources" items={registry.data_sources} />
              <RegistrySection title="Macro sources" items={registry.macro_sources} />
              <RegistrySection title="Fundamentals sources" items={registry.fundamentals_sources} />
              <RegistrySection title="Cache backends" items={registry.cache_backends} />
              <RegistrySection title="Universe providers" items={registry.universe_providers} />
              <RegistrySection title="Signals" items={registry.signals} />
              <RegistrySection title="Strategies" items={registry.strategies} />
            </>
          )}
        </aside>
      </div>
    </div>
  )
}

function RegistrySection({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="registry-section">
      <h4>{title}</h4>
      <ul>
        {items.map((item) => (
          <li key={item}>
            <code>{item}</code>
          </li>
        ))}
      </ul>
    </div>
  )
}
