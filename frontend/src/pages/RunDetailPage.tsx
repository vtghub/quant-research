import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, ApiError, fetchArtifact } from '../api/client'
import type { Run } from '../types'

const POLL_INTERVAL_MS = 2000

export function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>()
  const [run, setRun] = useState<Run | null>(null)
  const [error, setError] = useState<string | null>(null)
  const timerRef = useRef<number | null>(null)

  useEffect(() => {
    let cancelled = false

    async function poll() {
      try {
        const data = await api.get<Run>(`/runs/${runId}`)
        if (cancelled) return
        setRun(data)
        if (data.status === 'pending' || data.status === 'running') {
          timerRef.current = window.setTimeout(poll, POLL_INTERVAL_MS)
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : 'Failed to load run')
      }
    }

    poll()
    return () => {
      cancelled = true
      if (timerRef.current) window.clearTimeout(timerRef.current)
    }
  }, [runId])

  if (error) return <div className="page"><p className="error">{error}</p></div>
  if (!run) return <div className="page"><p className="muted">Loading…</p></div>

  const equityCurve = run.result_json?.equity_curve ?? []
  const metrics = run.result_json?.metrics
  const icSummary = run.result_json?.ic_summary
  const reportPaths = run.result_json?.report_paths ?? []

  return (
    <div className="page">
      <header className="topbar">
        <h1>Run #{run.id}</h1>
        <Link to="/">
          <button>Back to dashboard</button>
        </Link>
      </header>

      <section className="card">
        <p>
          <strong>Kind:</strong> {run.kind} &nbsp; <strong>Status:</strong>{' '}
          <span className={`badge badge-${run.status}`}>{run.status}</span>
        </p>
        {(run.status === 'pending' || run.status === 'running') && (
          <p className="muted">Polling every {POLL_INTERVAL_MS / 1000}s…</p>
        )}
        {run.error_message && <pre className="error">{run.error_message}</pre>}
      </section>

      {metrics && (
        <section className="card">
          <h2>Backtest metrics</h2>
          <table>
            <tbody>
              {Object.entries(metrics).map(([key, value]) => (
                <tr key={key}>
                  <td>{key}</td>
                  <td>{value === null ? '—' : value.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {equityCurve.length > 0 && (
        <section className="card">
          <h2>Equity curve</h2>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={equityCurve}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={false} />
              <YAxis domain={['auto', 'auto']} />
              <Tooltip />
              <Line type="monotone" dataKey="value" stroke="#4f7cff" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </section>
      )}

      {icSummary && (
        <section className="card">
          <h2>IC summary</h2>
          <table>
            <thead>
              <tr>
                <th>Horizon</th>
                <th>Mean IC</th>
                <th>IC IR</th>
                <th>t-stat</th>
                <th>Hit rate</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(icSummary).map(([horizon, summary]) => (
                <tr key={horizon}>
                  <td>{horizon}</td>
                  <td>{summary.mean_ic.toFixed(4)}</td>
                  <td>{summary.ic_ir.toFixed(4)}</td>
                  <td>{summary.t_stat.toFixed(2)}</td>
                  <td>{(summary.hit_rate * 100).toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {reportPaths.length > 0 && (
        <section className="card">
          <h2>Report artifacts</h2>
          <ul>
            {reportPaths.map((path) => {
              const filename = path.split('/').pop() ?? path
              return (
                <li key={path}>
                  <button className="link-button" onClick={() => fetchArtifact(run.id, filename)}>
                    {filename}
                  </button>
                </li>
              )
            })}
          </ul>
        </section>
      )}
    </div>
  )
}
