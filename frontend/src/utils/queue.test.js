import { describe, expect, it } from 'vitest'
import { queueArrivalGuidance } from './queue'

describe('adaptive arrival guidance', () => {
  it('prefers the calculated return window over generic guidance', () => {
    const result = queueArrivalGuidance({
      return_window_start: '2026-08-15T04:30:00Z',
      return_window_end: '2026-08-15T04:45:00Z',
      guidance: 'Stay nearby.',
    })
    expect(result).toMatch(/Recommended return window:/)
    expect(result).not.toBe('Stay nearby.')
  })

  it('uses safe onsite guidance when no calculated window exists', () => {
    expect(queueArrivalGuidance({ guidance: 'Follow reception instructions.' })).toBe(
      'Follow reception instructions.',
    )
    expect(queueArrivalGuidance()).toBe('Stay nearby and follow onsite staff guidance.')
  })
})
