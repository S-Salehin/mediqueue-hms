import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AssistantWidget } from './AssistantWidget'

const apiRequest = vi.fn()
let key = 0

vi.mock('../api/client', () => ({
  apiRequest: (...args) => apiRequest(...args),
  createIdempotencyKey: () => `test-message-${++key}`,
  payload: (result) => result.data,
  ApiError: class ApiError extends Error {},
}))

describe('AssistantWidget', () => {
  beforeEach(() => {
    apiRequest.mockReset()
    key = 0
  })

  it('opens with role-specific questions and closes with Escape', () => {
    render(
      <MemoryRouter>
        <AssistantWidget role="doctor" />
      </MemoryRouter>,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Open help assistant' }))
    expect(screen.getByRole('dialog', { name: 'Hospital help assistant' })).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'When is my patient pressure lowest this week?' }),
    ).toBeInTheDocument()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('submits a question and presents live sources and a safe action', async () => {
    apiRequest.mockResolvedValue({
      data: {
        answer: 'Dr Farhana Rahman has an open slot tomorrow at 10:00 AM.',
        sources: ['Live appointment capacity'],
        actions: [{ label: 'Book an appointment', path: '/patient/appointments/new' }],
        suggestions: ['How does the live queue work?'],
        provider: 'local',
        live_data: true,
        data_fresh_at: '2026-09-04T10:00:00Z',
      },
    })
    render(
      <MemoryRouter>
        <AssistantWidget role="patient" />
      </MemoryRouter>,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Open help assistant' }))
    fireEvent.change(screen.getByLabelText('Ask about this hospital system'), {
      target: { value: 'Which doctor is available tomorrow?' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send question' }))
    await waitFor(() => expect(screen.getByText(/Dr Farhana Rahman/)).toBeInTheDocument())
    expect(apiRequest).toHaveBeenCalledWith(
      '/assistant/chat/',
      expect.objectContaining({ method: 'POST', idempotent: false }),
    )
    expect(screen.getByText('Live hospital data')).toBeInTheDocument()
    expect(screen.getByText(/Sources: Live appointment capacity/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Book an appointment/ })).toHaveAttribute(
      'href',
      '/patient/appointments/new',
    )
  })
})
