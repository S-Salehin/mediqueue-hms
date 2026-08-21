import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useQueuePolling } from './useQueuePolling'

function snapshot(state = 'waiting') {
  return {
    queue_id: 'queue-1',
    ticket_id: 'ticket-1',
    token: 'A17',
    state,
    current_served_token: 'A13',
    people_ahead: 3,
    wait_lower_minutes: 18,
    wait_upper_minutes: 28,
    confidence: 'medium',
  }
}

function ok(body = snapshot()) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json', ETag: '"revision-1"' },
  })
}

describe('privacy-safe queue polling', () => {
  beforeEach(() => {
    Object.defineProperty(navigator, 'onLine', { value: true, configurable: true })
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('loads the personal snapshot and sends its ETag on the next visible poll', async () => {
    const intervalSpy = vi.spyOn(window, 'setInterval')
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(ok())
      .mockResolvedValueOnce(new Response(null, { status: 304, headers: { ETag: '"revision-1"' } }))
    vi.stubGlobal('fetch', fetchMock)
    const { result } = renderHook(() => useQueuePolling('queue-1'))
    await waitFor(() => expect(result.current.snapshot?.token).toBe('A17'))
    expect(intervalSpy).toHaveBeenCalledWith(expect.any(Function), 10_000)
    await act(async () => {
      await result.current.refresh()
    })
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls[1][1].headers.get('If-None-Match')).toBe('"revision-1"')
    expect(result.current.snapshot.current_served_token).toBe('A13')
  })

  it('marks retained data stale after the browser goes offline', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-08-15T05:00:00Z'))
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ok()))
    const { result } = renderHook(() => useQueuePolling('queue-1'))
    await act(async () => {
      await Promise.resolve()
      await Promise.resolve()
      await Promise.resolve()
    })
    expect(result.current.lastSuccess).not.toBeNull()
    Object.defineProperty(navigator, 'onLine', { value: false, configurable: true })
    act(() => window.dispatchEvent(new Event('offline')))
    vi.useFakeTimers()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(31_000)
    })
    expect(result.current.online).toBe(false)
    expect(result.current.stale).toBe(true)
    expect(result.current.snapshot.token).toBe('A17')

    Object.defineProperty(navigator, 'onLine', { value: true, configurable: true })
    await act(async () => {
      window.dispatchEvent(new Event('online'))
      await Promise.resolve()
      await Promise.resolve()
    })
    expect(result.current.online).toBe(true)
    expect(result.current.stale).toBe(false)
  })

  it('stops polling after a terminal queue state', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-08-15T05:00:00Z'))
    const fetchMock = vi.fn().mockResolvedValue(ok(snapshot('completed')))
    vi.stubGlobal('fetch', fetchMock)
    const { result } = renderHook(() => useQueuePolling('queue-1'))
    await act(async () => {
      await Promise.resolve()
      await Promise.resolve()
    })
    expect(result.current.terminal).toBe(true)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(40_000)
    })
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('announces a change to the canonical currently served token', async () => {
    const changed = { ...snapshot(), current_served_token: 'A14' }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(ok()).mockResolvedValueOnce(ok(changed)))
    const { result } = renderHook(() => useQueuePolling('queue-1'))
    await waitFor(() => expect(result.current.snapshot?.current_served_token).toBe('A13'))
    await act(async () => {
      await result.current.refresh()
    })
    expect(result.current.snapshot.current_served_token).toBe('A14')
    expect(result.current.announcement).toMatch(/queue status changed/i)
  })

  it('does not let an old queue request release a newer in-flight request', async () => {
    let resolveFirst
    let resolveSecond
    const first = new Promise((resolve) => {
      resolveFirst = resolve
    })
    const second = new Promise((resolve) => {
      resolveSecond = resolve
    })
    const fetchMock = vi.fn().mockReturnValueOnce(first).mockReturnValueOnce(second)
    vi.stubGlobal('fetch', fetchMock)
    const { result, rerender } = renderHook(({ queueId }) => useQueuePolling(queueId), {
      initialProps: { queueId: 'queue-1' },
    })
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    rerender({ queueId: 'queue-2' })
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    resolveFirst(ok({ ...snapshot(), queue_id: 'queue-1' }))
    await act(async () => {
      await first
      await Promise.resolve()
    })
    await act(async () => {
      await result.current.refresh()
    })
    expect(fetchMock).toHaveBeenCalledTimes(2)
    resolveSecond(ok({ ...snapshot(), queue_id: 'queue-2' }))
    await act(async () => {
      await second
      await Promise.resolve()
    })
    await waitFor(() => expect(result.current.snapshot?.queue_id).toBe('queue-2'))
  })
})
