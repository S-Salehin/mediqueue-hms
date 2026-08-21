import { Link } from 'react-router-dom'
import { useBrand } from '../context/BrandContext'
import { safeBrandLogoPath } from '../utils/format'

export function Brand({ compact = false }) {
  const brand = useBrand()
  const logoPath = safeBrandLogoPath(brand.logo_url)
  return (
    <Link to="/" className="brand" aria-label={`${brand.name} home`}>
      {logoPath ? (
        <img
          className="brand-mark brand-logo"
          src={logoPath}
          alt=""
          aria-hidden="true"
          decoding="async"
        />
      ) : (
        <svg className="brand-mark" viewBox="0 0 48 48" aria-hidden="true" focusable="false">
          <path
            d="M24 42C16.7 35.4 7 28.7 7 17.4 7 10.6 12.1 6 18.4 6c3.2 0 5.7 1.4 7.6 4 1.9-2.6 4.4-4 7.6-4C39.9 6 45 10.6 45 17.4 45 28.7 35.3 35.4 28 42l-2 1.8L24 42Z"
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            strokeLinejoin="round"
          />
          <path
            d="M24 15v12M18 21h12"
            stroke="currentColor"
            strokeWidth="3.5"
            strokeLinecap="round"
          />
        </svg>
      )}
      <span>
        <strong>{brand.name}</strong>
        {compact ? null : <small>{brand.tagline}</small>}
      </span>
    </Link>
  )
}
