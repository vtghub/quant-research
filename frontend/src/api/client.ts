const BASE = '/api'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function getToken(): string | null {
  return localStorage.getItem('qra_token')
}

export const getStoredToken = getToken

export function setToken(token: string | null): void {
  if (token) localStorage.setItem('qra_token', token)
  else localStorage.removeItem('qra_token')
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers = new Headers(options.headers)
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (options.body && !(options.body instanceof URLSearchParams)) {
    headers.set('Content-Type', 'application/json')
  }

  const resp = await fetch(`${BASE}${path}`, { ...options, headers })

  if (resp.status === 204) return undefined as T

  const isJson = resp.headers.get('content-type')?.includes('application/json')
  const body = isJson ? await resp.json() : await resp.text()

  if (!resp.ok) {
    const message = isJson && body?.detail ? JSON.stringify(body.detail) : String(body)
    throw new ApiError(resp.status, message)
  }
  return body as T
}

// Plain <a href> can't carry the Bearer token, so artifact downloads (which
// are behind the same auth as everything else) are fetched with the token
// attached and opened as a blob URL instead of linked directly.
export async function fetchArtifact(runId: number, filename: string): Promise<void> {
  const token = getToken()
  const headers = new Headers()
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const resp = await fetch(`${BASE}/runs/${runId}/artifacts/${encodeURIComponent(filename)}`, { headers })
  if (!resp.ok) {
    throw new ApiError(resp.status, `failed to fetch ${filename}`)
  }
  const blob = await resp.blob()
  const url = URL.createObjectURL(blob)
  window.open(url, '_blank')
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: 'POST', body: data !== undefined ? JSON.stringify(data) : undefined }),
  put: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: 'PUT', body: data !== undefined ? JSON.stringify(data) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  postForm: <T>(path: string, data: Record<string, string>) =>
    request<T>(path, { method: 'POST', body: new URLSearchParams(data) }),
}
