import { describe, expect, it } from 'vitest'
import {
  departmentName,
  doctorName,
  formatDate,
  formatDateTime,
  formatTime,
  getItems,
  hospitalDateInputValue,
  hospitalDateTimeInputValue,
  hospitalLocalDateTimeToIso,
  money,
  safeBrandLogoPath,
  tokenLabel,
} from './format'

describe('human-safe display formatting', () => {
  it('formats dates and times in the hospital display timezone', () => {
    expect(formatDate('2026-08-15T00:00:00Z')).toMatch(/Aug 15, 2026|15 Aug 2026/)
    expect(formatDateTime('2026-08-15T04:30:00Z')).toMatch(/Aug 15, 2026|15 Aug 2026/)
    expect(formatTime('2026-08-15T04:30:00Z')).toMatch(/10:30/)
    expect(formatTime('2026-08-15T03:00:00Z')).not.toContain('2026-08-15T')
  })

  it('keeps safe fallbacks for missing or non-date values', () => {
    expect(formatDate()).toBe('Not set')
    expect(formatDate('a hospital date')).toBe('a hospital date')
    expect(formatDateTime()).toBe('Not set')
    expect(formatTime('09:20')).toBe('09:20')
  })

  it('formats BDT minor units without inventing decimals', () => {
    expect(money(80000)).toContain('800')
    expect(money(80050)).toMatch(/800[.,]5/)
    expect(money(null)).toBe('Not set')
  })

  it('uses approved doctor and department display fields', () => {
    expect(doctorName({ display_name: 'Dr. Farhana Islam' })).toBe('Dr. Farhana Islam')
    expect(doctorName({ first_name: 'Nusrat', last_name: 'Jahan' })).toBe('Nusrat Jahan')
    expect(departmentName([{ name: 'Cardiology' }, { name: 'Medicine' }])).toBe(
      'Cardiology, Medicine',
    )
    expect(departmentName()).toBe('Not set')
  })

  it('makes queue tokens readable without changing their value', () => {
    expect(tokenLabel('A17')).toBe('A 17')
    expect(tokenLabel('DR01-017')).toBe('DR01 017')
    expect(tokenLabel('7')).toBe('7')
    expect(tokenLabel()).toBe('Not issued')
  })

  it('uses the hospital timezone for date input boundaries', () => {
    expect(hospitalDateInputValue('2026-08-14T18:30:00Z')).toBe('2026-08-15')
    expect(hospitalDateInputValue('not-a-date')).toBe('')
    expect(hospitalDateTimeInputValue('2026-08-14T18:30:00Z')).toBe('2026-08-15T00:30')
    expect(hospitalDateTimeInputValue('not-a-date')).toBe('')
    expect(hospitalLocalDateTimeToIso('2026-08-15T00:30')).toBe('2026-08-14T18:30:00.000Z')
    expect(hospitalLocalDateTimeToIso('not-a-local-time')).toBe('')
  })

  it('normalises common list containers', () => {
    expect(getItems([{ id: 1 }])).toEqual([{ id: 1 }])
    expect(getItems({ results: [{ id: 2 }] })).toEqual([{ id: 2 }])
    expect(getItems({ items: [{ id: 3 }] })).toEqual([{ id: 3 }])
  })

  it('allows only a same-origin logo path accepted by the service policy', () => {
    expect(safeBrandLogoPath('/branding/hospital-logo.svg')).toBe('/branding/hospital-logo.svg')
    expect(safeBrandLogoPath('https://images.example/logo.svg')).toBe('')
    expect(safeBrandLogoPath('//images.example/logo.svg')).toBe('')
    expect(safeBrandLogoPath('/branding/../private.svg')).toBe('')
    expect(safeBrandLogoPath('/branding/%2e%2e/private.svg')).toBe('')
    expect(safeBrandLogoPath('/branding/logo.svg?version=2')).toBe('')
  })
})
