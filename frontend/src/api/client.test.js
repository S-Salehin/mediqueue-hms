import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  ApiError,
  apiRequest,
  createWriteFingerprint,
  listPayload,
  payload,
  queryString,
} from './client'

function jsonResponse(body, init = {}) {
  return new Response(JSON.stringify(body), {
    status: init.status || 200,
    statusText: init.statusText,
    headers: { 'Content-Type': 'application/json', ...(init.headers || {}) },
  })
}

describe('API client', () => {
  beforeEach(() => {
    document.cookie = 'csrftoken=secure-csrf-value; path=/'
  })

  it('uses session cookies, CSRF, and an idempotency key for writes', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ id: 'appointment-1' }))
    vi.stubGlobal('fetch', fetchMock)
    const result = await apiRequest('/appointments/', {
      method: 'POST',
      body: { schedule_id: 'schedule-1' },
    })

    expect(payload(result)).toEqual({ id: 'appointment-1' })
    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v1/appointments/')
    expect(options.credentials).toBe('include')
    expect(options.headers.get('X-CSRFToken')).toBe('secure-csrf-value')
    expect(options.headers.get('Idempotency-Key')).toBeTruthy()
    expect(options.body).toBe(JSON.stringify({ schedule_id: 'schedule-1' }))
  })

  it('preserves the stable API error envelope', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            status: 409,
            code: 'slot_unavailable',
            title: 'Time no longer available',
            detail: 'Choose another open time.',
            field_errors: { start_at: ['This slot is full.'] },
            request_id: 'request-safe-123',
          },
          { status: 409 },
        ),
      ),
    )

    await expect(apiRequest('/appointments/', { method: 'POST', body: {} })).rejects.toMatchObject({
      name: 'ApiError',
      status: 409,
      code: 'slot_unavailable',
      fieldErrors: { start_at: ['This slot is full.'] },
      requestId: 'request-safe-123',
    })
  })

  it('turns connection failures into a privacy-safe network error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('internal browser detail')))
    await expect(apiRequest('/auth/session/')).rejects.toEqual(
      expect.objectContaining({
        code: 'network_unavailable',
        detail: 'Check your internet connection and try again.',
      }),
    )
  })

  it('reuses the same action key after an ambiguous connection failure', async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError('connection ended'))
      .mockResolvedValueOnce(jsonResponse({ saved: true }))
      .mockResolvedValueOnce(jsonResponse({ saved: true }))
    vi.stubGlobal('fetch', fetchMock)
    const options = { method: 'POST', body: { appointment_id: 'appointment-retry' } }
    await expect(apiRequest('/test/retry/', options)).rejects.toMatchObject({
      code: 'network_unavailable',
    })
    await expect(apiRequest('/test/retry/', options)).resolves.toBeTruthy()
    const firstKey = fetchMock.mock.calls[0][1].headers.get('Idempotency-Key')
    const retryKey = fetchMock.mock.calls[1][1].headers.get('Idempotency-Key')
    expect(retryKey).toBe(firstKey)
    await apiRequest('/test/retry/', options)
    expect(fetchMock.mock.calls[2][1].headers.get('Idempotency-Key')).not.toBe(firstKey)
  })

  it('reuses the action key while the server is still resolving the same operation', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(
          {
            status: 409,
            code: 'idempotency_in_progress',
            title: 'Action still in progress',
            detail: 'Try this action again shortly.',
          },
          { status: 409 },
        ),
      )
      .mockResolvedValueOnce(jsonResponse({ saved: true }))
    vi.stubGlobal('fetch', fetchMock)
    const options = { method: 'POST', body: { appointment_id: 'appointment-in-progress' } }

    await expect(apiRequest('/test/in-progress/', options)).rejects.toMatchObject({
      code: 'idempotency_in_progress',
    })
    await expect(apiRequest('/test/in-progress/', options)).resolves.toBeTruthy()

    const firstKey = fetchMock.mock.calls[0][1].headers.get('Idempotency-Key')
    const retryKey = fetchMock.mock.calls[1][1].headers.get('Idempotency-Key')
    expect(retryKey).toBe(firstKey)
  })

  it('fingerprints write identity without retaining the raw clinical or identity payload', async () => {
    const raw = JSON.stringify({
      patient_name: 'Private Patient',
      appointment_id: 'appointment-sensitive',
    })
    const first = await createWriteFingerprint('POST', '/appointments/', raw)
    const repeated = await createWriteFingerprint('POST', '/appointments/', raw)
    const changed = await createWriteFingerprint(
      'POST',
      '/appointments/',
      JSON.stringify({ patient_name: 'Another Patient' }),
    )

    expect(first).toBe(repeated)
    expect(first).not.toBe(changed)
    expect(first).not.toContain('Private Patient')
    expect(first).not.toContain('appointment-sensitive')
    expect(first).toMatch(/^[a-f0-9]{32,64}$/)
  })

  it('can disable idempotency for authentication and handle empty success responses', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)
    await expect(
      apiRequest('/auth/logout/', { method: 'POST', body: {}, idempotent: false }),
    ).resolves.toBeNull()
    expect(fetchMock.mock.calls[0][1].headers.has('Idempotency-Key')).toBe(false)
  })

  it('supports conditional queue responses without parsing a body', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(new Response(null, { status: 304, headers: { ETag: '"queue-7"' } })),
    )
    await expect(apiRequest('/queues/queue-1/snapshot/')).resolves.toEqual({
      notModified: true,
      etag: '"queue-7"',
    })
  })

  it('notifies the application when a protected session expires', async () => {
    const listener = vi.fn()
    window.addEventListener('mediqueue:session-expired', listener, { once: true })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            status: 401,
            code: 'not_authenticated',
            title: 'Sign in required',
            detail: 'Your session ended.',
          },
          { status: 401 },
        ),
      ),
    )
    await expect(apiRequest('/appointments/')).rejects.toMatchObject({ status: 401 })
    expect(listener).toHaveBeenCalledOnce()
  })

  it('normalises list envelopes and safe query values', () => {
    expect(listPayload({ data: { slots: [{ start_at: '2026-08-15T09:00:00Z' }] } })).toHaveLength(1)
    expect(queryString({ q: 'A B', empty: '', page: 2 })).toBe('?q=A+B&page=2')
    expect(new ApiError().message).toBe('Request failed')
  })
})
