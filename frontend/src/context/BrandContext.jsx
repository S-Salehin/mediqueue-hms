import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { apiRequest, payload } from '../api/client'
import { defaultBrand } from '../config'

const BrandContext = createContext(defaultBrand)

export function BrandProvider({ children }) {
  const [remote, setRemote] = useState({})
  const update = useCallback((next) => setRemote((current) => ({ ...current, ...next })), [])
  useEffect(() => {
    apiRequest('/public/hospital/')
      .then((result) => setRemote(payload(result) || {}))
      .catch(() => null)
  }, [])
  const brand = useMemo(
    () => ({
      ...defaultBrand,
      ...remote,
      name: remote.display_name || remote.name || defaultBrand.name,
      short_name: remote.short_name || defaultBrand.short_name,
      tagline: remote.tagline || remote.operational_settings?.tagline || defaultBrand.tagline,
      update,
    }),
    [remote, update],
  )
  useEffect(() => {
    document.title = brand.name
  }, [brand.name])
  return <BrandContext.Provider value={brand}>{children}</BrandContext.Provider>
}

export function useBrand() {
  return useContext(BrandContext)
}
