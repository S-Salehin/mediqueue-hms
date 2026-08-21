export function formatDate(value, options = {}) {
  if (!value) return 'Not set'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return new Intl.DateTimeFormat('en-BD', {
    dateStyle: options.dateStyle || 'medium',
    timeZone: 'Asia/Dhaka',
  }).format(date)
}

export function formatDateTime(value) {
  if (!value) return 'Not set'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return new Intl.DateTimeFormat('en-BD', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'Asia/Dhaka',
  }).format(date)
}

export function formatTime(value) {
  if (!value) return 'Not set'
  const date = new Date(value)
  if (!Number.isNaN(date.getTime()))
    return new Intl.DateTimeFormat('en-BD', {
      hour: 'numeric',
      minute: '2-digit',
      timeZone: 'Asia/Dhaka',
    }).format(date)
  return String(value).slice(0, 5)
}

export function money(amountMinor, currency = 'BDT') {
  if (amountMinor === undefined || amountMinor === null) return 'Not set'
  return new Intl.NumberFormat('en-BD', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(amountMinor / 100)
}

export function hospitalDateInputValue(value = new Date()) {
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Dhaka',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date)
  const part = (type) => parts.find((item) => item.type === type)?.value || ''
  return `${part('year')}-${part('month')}-${part('day')}`
}

export function hospitalDateTimeInputValue(value = new Date()) {
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Dhaka',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(date)
  const part = (type) => parts.find((item) => item.type === type)?.value || ''
  return `${part('year')}-${part('month')}-${part('day')}T${part('hour')}:${part('minute')}`
}

export function hospitalLocalDateTimeToIso(value) {
  const match = String(value || '').match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/)
  if (!match) return ''
  const [, year, month, day, hour, minute] = match.map((item, index) =>
    index ? Number(item) : item,
  )
  const timestamp = Date.UTC(year, month - 1, day, hour - 6, minute)
  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) return ''
  return date.toISOString()
}

function hasUnsafePathCharacters(value) {
  return [...value].some((character) => {
    const code = character.charCodeAt(0)
    return (
      character === '\\' || character === '?' || character === '#' || code <= 31 || code === 127
    )
  })
}

export function safeBrandLogoPath(value) {
  const path = String(value || '').trim()
  if (!path) return ''
  if (!path.startsWith('/') || path.startsWith('//')) return ''
  if (hasUnsafePathCharacters(path)) return ''

  let decoded
  try {
    decoded = decodeURIComponent(path)
  } catch {
    return ''
  }

  if (!decoded.startsWith('/') || decoded.startsWith('//')) return ''
  if (hasUnsafePathCharacters(decoded)) return ''
  if (decoded.split('/').some((part) => part === '.' || part === '..')) return ''
  return path
}

export function doctorName(doctor) {
  return (
    doctor?.display_name ||
    doctor?.full_name ||
    doctor?.name ||
    [doctor?.first_name, doctor?.last_name].filter(Boolean).join(' ') ||
    'Doctor'
  )
}

export function departmentName(value) {
  if (Array.isArray(value)) return value.map(departmentName).join(', ') || 'Not set'
  return typeof value === 'string' ? value : value?.name || value?.title || 'Not set'
}

export function tokenLabel(value) {
  if (!value) return 'Not issued'
  const token = String(value).trim()
  if (/^[A-Za-z]+\d+$/.test(token)) return token.replace(/^([A-Za-z]+)(\d+)$/, '$1 $2')
  return token.replace(/[-_]+/g, ' ')
}

export function getItems(value) {
  if (Array.isArray(value)) return value
  return value?.results || value?.items || []
}
