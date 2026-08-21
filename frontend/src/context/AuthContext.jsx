import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { apiRequest, payload } from '../api/client'

const AuthContext = createContext(null)

function normaliseUser(value) {
  const user = value?.user || value
  if (!user?.id && !user?.email) return null
  const sourceRoles = user.roles || value?.roles || (user.role ? [user.role] : [])
  return {
    ...user,
    roles: sourceRoles
      .map((role) => (typeof role === 'string' ? role : role.code || role.name))
      .filter(Boolean),
    permissions: user.permissions || value?.permissions || [],
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [status, setStatus] = useState('loading')
  const [error, setError] = useState(null)

  const refreshSession = useCallback(async () => {
    try {
      setError(null)
      const result = await apiRequest('/auth/session/')
      setUser(normaliseUser(payload(result)))
      setStatus('ready')
    } catch (requestError) {
      if (requestError.status === 401 || requestError.status === 403) {
        setUser(null)
        setStatus('ready')
        return null
      }
      setError(requestError)
      setStatus('error')
      throw requestError
    }
    return null
  }, [])

  useEffect(() => {
    apiRequest('/auth/csrf/')
      .catch(() => null)
      .finally(refreshSession)
      .catch(() => null)
  }, [refreshSession])

  useEffect(() => {
    const expire = () => {
      setUser(null)
      setStatus('ready')
    }
    window.addEventListener('mediqueue:session-expired', expire)
    return () => window.removeEventListener('mediqueue:session-expired', expire)
  }, [])

  const signIn = useCallback(
    async (credentials) => {
      const result = payload(
        await apiRequest('/auth/login/', { method: 'POST', body: credentials, idempotent: false }),
      )
      if (result?.mfa_required || result?.challenge_id) return { mfaRequired: true, ...result }
      const signedInUser = normaliseUser(result)
      if (signedInUser) {
        setUser(signedInUser)
        setStatus('ready')
      } else {
        await refreshSession()
      }
      return { mfaRequired: false, ...result }
    },
    [refreshSession],
  )

  const verifyMfa = useCallback(
    async (_challengeId, code) => {
      await apiRequest('/auth/mfa/verify/', { method: 'POST', body: { code }, idempotent: false })
      await refreshSession()
    },
    [refreshSession],
  )

  const signOut = useCallback(async () => {
    try {
      await apiRequest('/auth/logout/', { method: 'POST', body: {}, idempotent: false })
      setUser(null)
      setStatus('ready')
    } catch (requestError) {
      if (requestError.status === 401) {
        setUser(null)
        setStatus('ready')
        return
      }
      throw requestError
    }
  }, [])

  const hasRole = useCallback(
    (allowed) => {
      if (!allowed?.length) return true
      const current = user?.roles || []
      return allowed.some(
        (role) => current.includes(role) || (role === 'administrator' && current.includes('admin')),
      )
    },
    [user],
  )

  const value = useMemo(
    () => ({ user, status, error, signIn, verifyMfa, signOut, refreshSession, hasRole }),
    [user, status, error, signIn, verifyMfa, signOut, refreshSession, hasRole],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}
