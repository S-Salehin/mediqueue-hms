import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { ErrorSummary, Field, OfflineNotice } from './ui'

describe('accessible form errors', () => {
  it('focuses the summary and links each message to its field', async () => {
    render(
      <form>
        <ErrorSummary
          errors={{ full_name: ['Enter the patient name.'] }}
          fieldIds={{ full_name: 'patient-full-name' }}
        />
        <Field id="patient-full-name" label="Patient name">
          {(props) => <input {...props} />}
        </Field>
      </form>,
    )

    const summary = screen.getByRole('alert')
    expect(summary).toHaveFocus()
    const link = screen.getByRole('link', { name: /enter the patient name/i })
    expect(link).toHaveAttribute('href', '#patient-full-name')

    await userEvent.click(link)
    expect(screen.getByLabelText('Patient name')).toHaveFocus()
  })

  it('distinguishes an offline queue from a delayed online update', () => {
    const { rerender } = render(<OfflineNotice offline stale lastUpdated="10:30 AM" />)
    expect(screen.getByText('You are offline')).toBeInTheDocument()

    rerender(<OfflineNotice stale lastUpdated="10:30 AM" />)
    expect(screen.getByText('Queue update is delayed')).toBeInTheDocument()
    expect(screen.queryByText('You are offline')).not.toBeInTheDocument()
  })
})
