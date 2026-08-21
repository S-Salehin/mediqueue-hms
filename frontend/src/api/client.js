import { API_BASE_URL } from '../config'

export class ApiError extends Error {
  constructor({
    status = 0,
    code = 'request_failed',
    title = 'Request failed',
    detail = '',
    field_errors = {},
    request_id = '',
  } = {}) {
    super(detail || title)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.title = title
    this.detail = detail || title
    this.fieldErrors = field_errors || {}
    this.requestId = request_id
  }
}

function cookie(name) {
  return document.cookie
    .split(';')
    .map((item) => item.trim())
    .find((item) => item.startsWith(`${name}=`))
    ?.split('=')
    .slice(1)
    .join('=')
}

export function createIdempotencyKey() {
  return globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

const ambiguousWriteKeys = new Map()
const IDEMPOTENCY_RETRY_WINDOW_MS = 10 * 60 * 1000

function fallbackDigest(bytes) {
  const mask = (1n << 64n) - 1n
  const prime = 1099511628211n
  let first = 14695981039346656037n
  let second = 7809847782465536322n
  for (const byte of bytes) {
    first = ((first ^ BigInt(byte)) * prime) & mask
    second = ((second ^ BigInt(byte + 1)) * prime) & mask
  }
  return `${first.toString(16).padStart(16, '0')}${second.toString(16).padStart(16, '0')}`
}

export async function createWriteFingerprint(method, path, body) {
  const source = new TextEncoder().encode(
    `${method}\u0000${path}\u0000${typeof body === 'string' ? body : ''}`,
  )
  if (globalThis.crypto?.subtle) {
    const digest = await globalThis.crypto.subtle.digest('SHA-256', source)
    return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('')
  }
  return fallbackDigest(source)
}

async function retainedIdempotencyKey(method, path, body) {
  const now = Date.now()
  for (const [fingerprint, entry] of ambiguousWriteKeys) {
    if (now - entry.createdAt > IDEMPOTENCY_RETRY_WINDOW_MS) ambiguousWriteKeys.delete(fingerprint)
  }
  const fingerprint = await createWriteFingerprint(method, path, body)
  const existing = ambiguousWriteKeys.get(fingerprint)
  if (existing) return { fingerprint, key: existing.key }
  const key = createIdempotencyKey()
  ambiguousWriteKeys.set(fingerprint, { key, createdAt: now })
  return { fingerprint, key }
}

async function parseError(response) {
  let body
  try {
    body = await response.json()
  } catch {
    body = {}
  }
  const nested = body.error || body
  return new ApiError({
    status: response.status,
    code: nested.code || `http_${response.status}`,
    title: nested.title || response.statusText || 'Request failed',
    detail: nested.detail || nested.message || 'The request could not be completed.',
    field_errors: nested.field_errors || nested.errors || {},
    request_id: nested.request_id || response.headers.get('X-Request-ID') || '',
  })
}

export async function apiRequest(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase()
  const headers = new Headers(options.headers || {})
  headers.set('Accept', 'application/json')

  let body = options.body
  if (body && !(body instanceof FormData) && typeof body !== 'string') {
    headers.set('Content-Type', 'application/json')
    body = JSON.stringify(body)
  }

  let retainedWrite = null
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    const csrfToken = decodeURIComponent(cookie('csrftoken') || '')
    if (csrfToken) headers.set('X-CSRFToken', csrfToken)
    if (options.idempotent !== false) {
      if (options.idempotencyKey) headers.set('Idempotency-Key', options.idempotencyKey)
      else {
        retainedWrite = await retainedIdempotencyKey(method, path, body)
        headers.set('Idempotency-Key', retainedWrite.key)
      }
    }
  }

  let response
  try {
    response = await fetch(`${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`, {
      ...options,
      method,
      headers,
      body,
      credentials: 'include',
      cache: 'no-store',
    })
  } catch (error) {
    if (error?.name === 'AbortError') throw error
    throw new ApiError({
      code: 'network_unavailable',
      title: 'Connection unavailable',
      detail: 'Check your internet connection and try again.',
    })
  }

  if (response.status === 304) {
    return { notModified: true, etag: response.headers.get('ETag') }
  }
  if (!response.ok) {
    const error = await parseError(response)
    if (retainedWrite && response.status < 500 && error.code !== 'idempotency_in_progress') {
      ambiguousWriteKeys.delete(retainedWrite.fingerprint)
    }
    if (response.status === 401 && !path.startsWith('/auth/')) {
      window.dispatchEvent(new CustomEvent('mediqueue:session-expired'))
    }
    throw error
  }
  if (retainedWrite) ambiguousWriteKeys.delete(retainedWrite.fingerprint)
  if (response.status === 204) return null

  const contentType = response.headers.get('Content-Type') || ''
  const data = contentType.includes('application/json') ? await response.json() : null
  return {
    data,
    etag: response.headers.get('ETag'),
    requestId: response.headers.get('X-Request-ID'),
  }
}

export function payload(result) {
  const body = result?.data ?? result
  return body?.data ?? body?.result ?? body
}

export function listPayload(result) {
  const body = payload(result)
  if (Array.isArray(body)) return body
  return body?.results || body?.items || body?.slots || body?.possible_matches || []
}

export function queryString(values) {
  const params = new URLSearchParams()
  Object.entries(values).forEach(([key, value]) => {
    if (value !== '' && value !== undefined && value !== null) params.set(key, value)
  })
  const text = params.toString()
  return text ? `?${text}` : ''
}
