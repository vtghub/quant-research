import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import type { Run, SavedConfig } from '../types'

const STATUS_CLASS: Record<Run['status'], string> = {
  pending: 'badge badge-pending',
  running: 'badge badge-running',
  success: 'badge badge-success',
  failed: 'badge badge-failed',
}

export function DashboardPage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [configs, setConfigs] = useState<SavedConfig[]>([])
  const [runs, setRuns] = useState<Run[]>([])
  const [error, setError] = useState<string | null>(null)
  const [runningConfigId, setRunningConfigId] = useState<number | null>(null)

  const refresh = useCallback(async () => {
    try {
      const [configsResp, runsResp] = await Promise.all([
        api.get<SavedConfig[]>('/configs'),
        api.get<Run[]>('/runs'),
      ])
      setConfigs(configsResp)
      setRuns(runsResp)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load dashboard')
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  async function triggerRun(configId: number, kind: 'research' | 'backtest') {
    setRunningConfigId(configId)
    try {
      const run = await api.post<Run>('/runs', { config_id: configId, kind })
      navigate(`/runs/${run.id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to start run')
    } finally {
      setRunningConfigId(null)
    }
  }

  async function deleteConfig(configId: number) {
    if (!confirm('Delete this saved config?')) return
    await api.delete(`/configs/${configId}`)
    refresh()
  }

  return (
    <div className="page">
      <header className="topbar">
        <h1>quant-research</h1>
        <div className="topbar-right">
          <span className="muted">{user?.email}</span>
          <button onClick={logout}>Log out</button>
        </div>
      </header>

      {error && <p className="error">{error}</p>}

      <section className="card">
        <div className="card-header">
          <h2>Saved configs</h2>
          <Link to="/configs/new">
            <button>New config</button>
          </Link>
        </div>
        {configs.length === 0 ? (
          <p className="muted">No saved configs yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Updated</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {configs.map((config) => (
                <tr key={config.id}>
                  <td>{config.name}</td>
                  <td className="muted">{new Date(config.updated_at).toLocaleString()}</td>
                  <td className="row-actions">
                    <button
                      disabled={runningConfigId === config.id}
                      onClick={() => triggerRun(config.id, 'research')}
                    >
                      Research
                    </button>
                    <button
                      disabled={runningConfigId === config.id}
                      onClick={() => triggerRun(config.id, 'backtest')}
                    >
                      Backtest
                    </button>
                    <Link to={`/configs/${config.id}`}>
                      <button>Edit</button>
                    </Link>
                    <button className="danger" onClick={() => deleteConfig(config.id)}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="card">
        <h2>Run history</h2>
        {runs.length === 0 ? (
          <p className="muted">No runs yet -- trigger one from a saved config above.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Kind</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id} className="clickable" onClick={() => navigate(`/runs/${run.id}`)}>
                  <td>{run.id}</td>
                  <td>{run.kind}</td>
                  <td>
                    <span className={STATUS_CLASS[run.status]}>{run.status}</span>
                  </td>
                  <td className="muted">{new Date(run.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}
