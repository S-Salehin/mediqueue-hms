import { useCallback, useEffect, useRef, useState } from 'react'
import { apiRequest, listPayload, payload } from '../api/client'

export function useResource(path, { list = false, enabled = true } = {}) {
  const [data, setData] = useState(list ? [] : null)
  const [loading, setLoading] = useState(enabled)
  const [error, setError] = useState(null)
  const requestSequence = useRef(0)

  const load = useCallback(async () => {
    const sequence = ++requestSequence.current
    if (!enabled || !path) {
      setLoading(false)
      setError(null)
      setData(list ? [] : null)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const result = await apiRequest(path)
      if (requestSequence.current === sequence) {
        setData(list ? listPayload(result) : payload(result))
      }
    } catch (requestError) {
      if (requestSequence.current === sequence) setError(requestError)
    } finally {
      if (requestSequence.current === sequence) setLoading(false)
    }
  }, [enabled, list, path])

  useEffect(() => {
    load()
    return () => {
      requestSequence.current += 1
    }
  }, [load])

  return { data, setData, loading, error, reload: load }
}
