import { useCallback, useEffect, useRef, useState } from 'react'
import { apiRequest, payload } from '../api/client'

const TERMINAL_STATES = new Set(['completed', 'no_show', 'cancelled'])

export function useQueuePolling(queueId, { enabled = true } = {}) {
  const [snapshot, setSnapshot] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(Boolean(enabled && queueId))
  const [online, setOnline] = useState(navigator.onLine)
  const [lastSuccess, setLastSuccess] = useState(null)
  const [clock, setClock] = useState(0)
  const [announcement, setAnnouncement] = useState('')
  const etag = useRef(null)
  const requestSequence = useRef(0)
  const inFlight = useRef(null)
  const previousMeaningful = useRef('')
  const state = snapshot?.state || snapshot?.status
  const terminal = TERMINAL_STATES.has(state)

  const refresh = useCallback(async () => {
    if (!enabled || !queueId || !navigator.onLine || inFlight.current === requestSequence.current)
      return
    const sequence = requestSequence.current
    inFlight.current = sequence
    try {
      const result = await apiRequest(`/queues/${queueId}/snapshot/`, {
        headers: etag.current ? { 'If-None-Match': etag.current } : {},
      })
      if (sequence !== requestSequence.current) return
      if (result?.etag) etag.current = result.etag
      if (!result?.notModified) {
        const next = payload(result)
        const ownToken = next?.token || next?.ticket_token || ''
        const currentToken =
          next?.current_served_token ||
          next?.currently_serving ||
          next?.current_token ||
          next?.current_ticket?.token ||
          next?.current?.token ||
          ''
        const nextState =
          next?.state || next?.status || next?.current_ticket?.state || next?.current?.state || ''
        const waitingCount = (next?.tickets || []).filter(
          (ticket) => ticket.state === 'waiting',
        ).length
        const meaningful = `${ownToken}:${currentToken}:${nextState}:${next?.revision ?? ''}:${waitingCount}`
        if (previousMeaningful.current && meaningful !== previousMeaningful.current) {
          setAnnouncement(
            ownToken
              ? `Queue status changed. Your token ${ownToken} is ${nextState || 'updated'}. ${currentToken ? `Currently serving ${currentToken}.` : 'No token is currently being served.'}`
              : `Queue status changed. ${currentToken ? `Current token ${currentToken}.` : 'No active token.'} ${waitingCount} waiting.`,
          )
        }
        previousMeaningful.current = meaningful
        setSnapshot(next)
      }
      const successTime = new Date()
      setLastSuccess(successTime)
      setClock(successTime.getTime())
      setError(null)
    } catch (requestError) {
      if (sequence === requestSequence.current) setError(requestError)
    } finally {
      if (sequence === requestSequence.current) setLoading(false)
      if (inFlight.current === sequence) inFlight.current = null
    }
  }, [enabled, queueId])

  useEffect(() => {
    requestSequence.current += 1
    inFlight.current = null
    etag.current = null
    previousMeaningful.current = ''
    setSnapshot(null)
    setError(null)
    setLastSuccess(null)
    setAnnouncement('')
    setLoading(Boolean(enabled && queueId))
  }, [enabled, queueId])

  useEffect(() => {
    if (!enabled || !queueId || terminal) return undefined
    refresh()
    const schedule = () =>
      window.setInterval(refresh, document.visibilityState === 'visible' ? 10_000 : 30_000)
    let interval = schedule()
    const visibility = () => {
      window.clearInterval(interval)
      if (document.visibilityState === 'visible') refresh()
      interval = schedule()
    }
    const connected = () => {
      setOnline(true)
      refresh()
    }
    const disconnected = () => setOnline(false)
    document.addEventListener('visibilitychange', visibility)
    window.addEventListener('online', connected)
    window.addEventListener('offline', disconnected)
    return () => {
      window.clearInterval(interval)
      document.removeEventListener('visibilitychange', visibility)
      window.removeEventListener('online', connected)
      window.removeEventListener('offline', disconnected)
    }
  }, [enabled, queueId, refresh, terminal])

  useEffect(() => {
    const timer = window.setInterval(() => setClock(Date.now()), 1_000)
    return () => window.clearInterval(timer)
  }, [])

  const stale = !online || !lastSuccess || clock - lastSuccess.getTime() > 30_000
  return { snapshot, error, loading, online, stale, lastSuccess, refresh, announcement, terminal }
}
