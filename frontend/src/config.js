export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')

export const defaultBrand = {
  name: import.meta.env.VITE_APP_CODENAME || 'MediQueue',
  tagline: 'Care that respects your time',
  short_name: 'MQ',
  phone: '',
  email: '',
  address: '',
  logo_url: '',
}

export const roles = {
  patient: 'Patient',
  doctor: 'Doctor',
  receptionist: 'Reception',
  administrator: 'Administration',
  admin: 'Administration',
}
