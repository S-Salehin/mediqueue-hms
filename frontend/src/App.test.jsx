import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

function response(body, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }),
  )
}

function apiMock(session) {
  return vi.fn((url) => {
    if (url.endsWith('/auth/session/')) return response(session)
    if (url.endsWith('/auth/csrf/')) return response({ csrf_token: 'test' })
    if (url.endsWith('/public/hospital/'))
      return response({ name: 'Hospital Pilot', tagline: 'Care that respects your time' })
    if (url.endsWith('/dashboards/administrator/'))
      return response({ role: 'administrator', summary: {}, recent: [] })
    return response([])
  })
}

describe('application routing and identity', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/')
  })

  it('renders the public service without false queue identity claims', async () => {
    vi.stubGlobal(
      'fetch',
      apiMock({ authenticated: false, user: null, roles: [], permissions: [] }),
    )
    render(<App />)
    expect(
      screen.getByRole('heading', { name: /your visit should begin with clarity/i }),
    ).toBeInTheDocument()
    expect(screen.getByText(/no other patient names shown/i)).toBeInTheDocument()
    expect(screen.queryByText('Rahim Uddin')).not.toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /skip to main content/i })).toHaveLength(1)
    await waitFor(() => expect(document.title).toBe('Hospital Pilot'))
  })

  it('redirects an unauthenticated protected route to the unified sign in', async () => {
    window.history.replaceState({}, '', '/patient')
    vi.stubGlobal(
      'fetch',
      apiMock({ authenticated: false, user: null, roles: [], permissions: [] }),
    )
    render(<App />)
    expect(
      await screen.findByRole('heading', { name: 'Sign in to your account' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/role assigned to your account/i)).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /skip to main content/i })).toHaveLength(1)
  })

  it('shows only the administration navigation for an administrator', async () => {
    window.history.replaceState({}, '', '/admin')
    vi.stubGlobal(
      'fetch',
      apiMock({
        authenticated: true,
        user: { id: 'user-1', email: 'admin@example.test', display_name: 'Hospital Admin' },
        roles: ['administrator'],
        permissions: [],
        mfa_verified: true,
      }),
    )
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Operational overview' })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'administrator navigation' })).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /skip to main content/i })).toHaveLength(1)
    expect(screen.queryByRole('link', { name: 'My profile' })).not.toBeInTheDocument()
    await waitFor(() =>
      expect(document.activeElement).toBe(document.querySelector('#main-content')),
    )
  })

  it('submits the unified sign in form without storing an auth token', async () => {
    window.history.replaceState({}, '', '/sign-in')
    const fetchMock = vi.fn((url, options = {}) => {
      if (url.endsWith('/auth/session/'))
        return response({ authenticated: false, user: null, roles: [] })
      if (url.endsWith('/auth/csrf/')) return response({ csrf_token: 'test' })
      if (url.endsWith('/public/hospital/')) return response({ name: 'Hospital Pilot' })
      if (url.endsWith('/auth/login/') && options.method === 'POST')
        return response({
          user: { id: 'patient-1', email: 'patient@example.test', display_name: 'Patient User' },
          roles: ['patient'],
        })
      if (url.endsWith('/dashboards/patient/'))
        return response({ role: 'patient', summary: {}, recent: [] })
      return response([])
    })
    vi.stubGlobal('fetch', fetchMock)
    const storageSpy = vi.spyOn(Storage.prototype, 'setItem')
    render(<App />)
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText(/email address/i), 'patient@example.test')
    await user.type(screen.getByLabelText(/^password/i), 'A long patient password')
    await user.click(screen.getByRole('button', { name: /^sign in/i }))
    expect(await screen.findByRole('heading', { name: /hello/i })).toBeInTheDocument()
    expect(storageSpy).not.toHaveBeenCalled()
  })

  it('routes staff invitations to the protected account setup flow', async () => {
    window.history.replaceState({}, '', '/accept-invitation?token=abcdefghijklmnopqrstuvwxyz123456')
    vi.stubGlobal('fetch', apiMock({ authenticated: false, user: null, roles: [] }))
    render(<App />)
    expect(
      await screen.findByRole('heading', { name: 'Accept your invitation' }),
    ).toBeInTheDocument()
    expect(screen.getByLabelText(/display name/i)).toBeInTheDocument()
  })

  it('requests a replacement verification link without exposing account existence', async () => {
    window.history.replaceState({}, '', '/resend-verification')
    const fetchMock = vi.fn((url, options = {}) => {
      if (url.endsWith('/auth/session/'))
        return response({ authenticated: false, user: null, roles: [] })
      if (url.endsWith('/auth/csrf/')) return response({ csrf_token: 'test' })
      if (url.endsWith('/public/hospital/')) return response({ display_name: 'Hospital Pilot' })
      if (url.endsWith('/auth/email/resend/') && options.method === 'POST')
        return response({ accepted: true })
      return response([])
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText(/email address/i), 'patient@example.test')
    await user.click(screen.getByRole('button', { name: 'Send verification link' }))
    expect(await screen.findByText(/matches an unverified account/i)).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([url]) => url.endsWith('/auth/email/resend/'))).toBe(true)
  })

  it('unwraps staff MFA enrollment details after invitation acceptance', async () => {
    window.history.replaceState({}, '', '/accept-invitation?token=abcdefghijklmnopqrstuvwxyz123456')
    const fetchMock = vi.fn((url, options = {}) => {
      if (url.endsWith('/auth/session/'))
        return response({ authenticated: false, user: null, roles: [] })
      if (url.endsWith('/auth/csrf/')) return response({ csrf_token: 'test' })
      if (url.endsWith('/public/hospital/')) return response({ display_name: 'Hospital Pilot' })
      if (url.endsWith('/auth/staff-invitations/accept/') && options.method === 'POST') {
        return response({
          provisioning_uri: 'otpauth://totp/Hospital%20Pilot',
          totp_secret: 'TESTSECRET123',
        })
      }
      return response([])
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText(/display name/i), 'Doctor One')
    await user.type(screen.getByLabelText(/^password/i), 'A secure invitation passphrase')
    await user.type(screen.getByLabelText(/confirm password/i), 'A secure invitation passphrase')
    await user.click(screen.getByRole('button', { name: /create staff account/i }))
    expect(await screen.findByText('otpauth://totp/Hospital%20Pilot')).toBeInTheDocument()
    expect(screen.getByText('TESTSECRET123')).toBeInTheDocument()
  })

  it('shows the exact active privacy notice as plain text', async () => {
    window.history.replaceState({}, '', '/privacy')
    const mock = apiMock({ authenticated: false, user: null, roles: [] })
    mock.mockImplementation((url) => {
      if (url.endsWith('/auth/session/'))
        return response({ authenticated: false, user: null, roles: [] })
      if (url.endsWith('/auth/csrf/')) return response({ csrf_token: 'test' })
      if (url.endsWith('/public/hospital/'))
        return response({
          display_name: 'Hospital Pilot',
          privacy_notice: {
            id: 'notice-1',
            title: 'Hospital privacy notice',
            version: '3',
            effective_at: '2026-08-15T00:00:00Z',
            content: 'This is the exact approved notice text.',
          },
        })
      return response([])
    })
    vi.stubGlobal('fetch', mock)
    render(<App />)
    expect(
      await screen.findByRole('heading', { name: 'Hospital privacy notice' }),
    ).toBeInTheDocument()
    expect(screen.getByText('This is the exact approved notice text.')).toBeInTheDocument()
  })

  it('renders the canonical patient dashboard summary value', async () => {
    window.history.replaceState({}, '', '/patient')
    const fetchMock = vi.fn((url) => {
      if (url.endsWith('/auth/session/'))
        return response({
          authenticated: true,
          user: { id: 'patient-1', email: 'patient@example.test', display_name: 'Patient User' },
          roles: ['patient'],
          mfa_verified: false,
          permissions: [],
        })
      if (url.endsWith('/auth/csrf/')) return response({ csrf_token: 'test' })
      if (url.endsWith('/public/hospital/')) return response({ display_name: 'Hospital Pilot' })
      if (url.endsWith('/dashboards/patient/'))
        return response({ role: 'patient', summary: { upcoming_appointments: 7 }, recent: [] })
      return response([])
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    expect(await screen.findByText('Upcoming')).toBeInTheDocument()
    expect(screen.getByText('7')).toBeInTheDocument()
  })

  it('replaces staff MFA only after password, recovery-code acknowledgement, and a new code', async () => {
    window.history.replaceState({}, '', '/doctor/security')
    const fetchMock = vi.fn((url, options = {}) => {
      if (url.endsWith('/auth/session/'))
        return response({
          authenticated: true,
          user: { id: 'doctor-user', email: 'doctor@example.test', display_name: 'Doctor One' },
          roles: ['doctor'],
          mfa_verified: true,
        })
      if (url.endsWith('/auth/csrf/')) return response({ csrf_token: 'test' })
      if (url.endsWith('/public/hospital/')) return response({ display_name: 'Hospital Pilot' })
      if (url.endsWith('/auth/mfa/replacement/start/') && options.method === 'POST')
        return response(
          {
            provisioning_uri: 'otpauth://totp/replacement',
            totp_secret: 'NEWSECRET123',
            recovery_codes: ['SAFE-CODE-1', 'SAFE-CODE-2'],
          },
          201,
        )
      if (url.endsWith('/auth/mfa/replacement/confirm/') && options.method === 'POST')
        return response({ replaced: true })
      return response([])
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText(/Current password/i), 'current staff password')
    await user.click(screen.getByRole('button', { name: 'Start secure replacement' }))
    expect(await screen.findByText('SAFE-CODE-1')).toBeInTheDocument()
    const confirm = screen.getByRole('button', { name: 'Confirm replacement' })
    expect(confirm).toBeDisabled()
    await user.click(screen.getByLabelText(/I saved these recovery codes/i))
    await user.type(screen.getByLabelText(/Six-digit code from the new authenticator/i), '123456')
    expect(confirm).toBeEnabled()
    await user.click(confirm)
    expect(await screen.findByText(/previous set no longer works/i)).toBeInTheDocument()
    const request = fetchMock.mock.calls.find(([url]) =>
      url.endsWith('/auth/mfa/replacement/confirm/'),
    )
    expect(JSON.parse(request[1].body)).toEqual({ code: '123456' })
  })

  it('requires an explicit unselected patient decision for assisted consent', async () => {
    window.history.replaceState({}, '', '/reception/patients')
    const fetchMock = vi.fn((url, options = {}) => {
      if (url.endsWith('/auth/session/'))
        return response({
          authenticated: true,
          user: {
            id: 'reception-user',
            email: 'reception@example.test',
            display_name: 'Reception One',
          },
          roles: ['receptionist'],
          mfa_verified: true,
        })
      if (url.endsWith('/auth/csrf/')) return response({ csrf_token: 'test' })
      if (url.endsWith('/public/hospital/'))
        return response({
          display_name: 'Hospital Pilot',
          privacy_notice: {
            id: 'notice-1',
            version: '3',
            title: 'Current privacy notice',
            content: 'Approved notice.',
          },
        })
      if (url.includes('/reception/patients/?q='))
        return response([
          {
            id: 'patient-1',
            mrn: 'MRN-000001',
            full_name: 'Patient One',
            date_of_birth: '1990-01-01',
            phone: '+8801700000000',
            email: 'patient@example.test',
            is_active: true,
            is_claimed: true,
          },
        ])
      if (url.endsWith('/reception/patients/patient-1/consents/') && options.method === 'POST')
        return response({ id: 'consent-1', purpose: 'email_notifications', decision: false }, 201)
      return response([])
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    const user = userEvent.setup()
    const search = await screen.findByLabelText('Search patient records')
    await user.type(search, 'Patient One')
    await user.click(screen.getByRole('button', { name: /^search$/i }))
    expect(await screen.findByText('MRN-000001')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Record consent' }))
    const dialog = screen.getByRole('dialog')
    const decision = within(dialog).getByLabelText(/Patient decision/i)
    expect(decision).toHaveValue('')
    expect(within(dialog).getByRole('button', { name: 'Record decision' })).toBeDisabled()
    await user.selectOptions(decision, 'decline')
    await user.click(within(dialog).getByRole('button', { name: 'Record decision' }))
    expect(await screen.findByText(/decision was recorded/i)).toBeInTheDocument()
    const request = fetchMock.mock.calls.find(([url]) =>
      url.endsWith('/reception/patients/patient-1/consents/'),
    )
    expect(JSON.parse(request[1].body)).toEqual({
      notice_version_id: 'notice-1',
      purpose: 'email_notifications',
      decision: false,
    })
  })

  it('hides pre-check-in appointment changes after a queue token is issued', async () => {
    window.history.replaceState({}, '', '/patient/appointments/appointment-1')
    const fetchMock = vi.fn((url) => {
      if (url.endsWith('/auth/session/'))
        return response({
          authenticated: true,
          user: { id: 'patient-user', email: 'patient@example.test' },
          roles: ['patient'],
        })
      if (url.endsWith('/auth/csrf/')) return response({ csrf_token: 'test' })
      if (url.endsWith('/public/hospital/')) return response({ display_name: 'Hospital Pilot' })
      if (url.endsWith('/appointments/appointment-1/'))
        return response({
          id: 'appointment-1',
          status: 'confirmed',
          start_at: '2026-08-16T04:00:00Z',
          doctor: { display_name: 'Doctor One' },
          department: { name: 'Medicine' },
          location: { name: 'Main hospital' },
          chamber: { name: 'Room 1' },
          queue_ticket: { session: 'queue-1', state: 'waiting' },
        })
      if (url.endsWith('/appointments/appointment-1/payment/'))
        return response({ state: 'unpaid', amount_minor: 50000, currency: 'BDT' })
      return response([])
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    expect(await screen.findByRole('link', { name: /Open live queue/i })).toHaveAttribute(
      'href',
      '/patient/queue/queue-1',
    )
    expect(screen.queryByRole('link', { name: 'Reschedule' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Cancel appointment' })).not.toBeInTheDocument()
  })

  it('clears a stale walk-in patient when a new search is applied', async () => {
    window.history.replaceState({}, '', '/reception/appointments')
    const fetchMock = vi.fn((url) => {
      if (url.endsWith('/auth/session/'))
        return response({
          authenticated: true,
          user: { id: 'reception-user', email: 'reception@example.test' },
          roles: ['receptionist'],
          mfa_verified: true,
        })
      if (url.endsWith('/auth/csrf/')) return response({ csrf_token: 'test' })
      if (url.endsWith('/public/hospital/')) return response({ display_name: 'Hospital Pilot' })
      if (url.endsWith('/public/departments/'))
        return response([{ id: 'department-1', name: 'Medicine' }])
      if (url.endsWith('/public/doctors/'))
        return response([
          {
            id: 'doctor-1',
            display_name: 'Doctor One',
            departments: [{ id: 'department-1', name: 'Medicine' }],
          },
        ])
      if (url.includes('/reception/patients/?q=Patient'))
        return response([
          {
            id: 'patient-1',
            mrn: 'MRN-000001',
            full_name: 'Patient One',
            date_of_birth: '1990-01-01',
          },
        ])
      if (url.includes('/reception/patients/?q=Missing')) return response([])
      if (url.includes('/public/doctors/doctor-1/availability/'))
        return response({
          slots: [
            { schedule_id: 'schedule-1', start_at: '2026-08-15T04:00:00Z', available_capacity: 1 },
          ],
        })
      if (url.includes('/appointments/')) return response([])
      return response([])
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Add walk-in' }))
    const patientSearch = screen.getByLabelText(/Find patient/i)
    const patientSearchArea = patientSearch.closest('.field')
    await user.type(patientSearch, 'Patient')
    await user.click(within(patientSearchArea).getByRole('button', { name: 'Search' }))
    await user.click(await screen.findByRole('radio', { name: /Patient One/i }))
    await user.selectOptions(screen.getByLabelText(/Department/i), 'department-1')
    await user.selectOptions(screen.getByLabelText(/Doctor/i), 'doctor-1')
    await waitFor(() =>
      expect(screen.getByLabelText(/Available time/i).options.length).toBeGreaterThan(1),
    )
    await user.selectOptions(screen.getByLabelText(/Available time/i), '2026-08-15T04:00:00Z')
    const submit = screen.getByRole('button', { name: /Create walk-in and check in/i })
    expect(submit).toBeEnabled()
    await user.clear(patientSearch)
    await user.type(patientSearch, 'Missing')
    await user.click(within(patientSearchArea).getByRole('button', { name: 'Search' }))
    await waitFor(() =>
      expect(screen.queryByRole('radio', { name: /Patient One/i })).not.toBeInTheDocument(),
    )
    expect(submit).toBeDisabled()
  })

  it('requires a reason and retries failed notification jobs only', async () => {
    window.history.replaceState({}, '', '/admin/notifications')
    const fetchMock = vi.fn((url, options = {}) => {
      if (url.endsWith('/auth/session/'))
        return response({
          authenticated: true,
          user: { id: 'admin-user', email: 'admin@example.test' },
          roles: ['administrator'],
          mfa_verified: true,
        })
      if (url.endsWith('/auth/csrf/')) return response({ csrf_token: 'test' })
      if (url.endsWith('/public/hospital/')) return response({ display_name: 'Hospital Pilot' })
      if (url.endsWith('/admin/notification-outbox/'))
        return response([
          {
            id: 'job-failed',
            template_key: 'appointment_changed',
            state: 'failed',
            attempt_count: 2,
            created_at: '2026-08-15T04:00:00Z',
          },
          {
            id: 'job-dead',
            template_key: 'password_reset',
            state: 'dead',
            attempt_count: 5,
            created_at: '2026-08-15T03:00:00Z',
          },
        ])
      if (url.endsWith('/admin/notification-outbox/job-failed/retry/') && options.method === 'POST')
        return response({ id: 'job-failed', state: 'pending', attempt_count: 2 })
      return response([])
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    const user = userEvent.setup()
    const retry = await screen.findByRole('button', { name: 'Retry safely' })
    expect(screen.getAllByRole('button', { name: 'Retry safely' })).toHaveLength(1)
    expect(screen.getByText(/Restart the original invitation/i)).toBeInTheDocument()
    await user.click(retry)
    const dialog = screen.getByRole('dialog')
    const confirm = within(dialog).getByRole('button', { name: 'Return to queue' })
    expect(confirm).toBeDisabled()
    await user.type(within(dialog).getByLabelText(/Operational reason/i), 'SMTP service restored')
    await user.click(confirm)
    expect(await screen.findByText(/returned to the notification queue/i)).toBeInTheDocument()
    const request = fetchMock.mock.calls.find(([url]) =>
      url.endsWith('/admin/notification-outbox/job-failed/retry/'),
    )
    expect(JSON.parse(request[1].body)).toEqual({ reason: 'SMTP service restored' })
  })

  it('requires a nonclinical reason before a patient can leave a checked-in queue', async () => {
    window.history.replaceState({}, '', '/patient/queue/queue-1')
    let left = false
    const fetchMock = vi.fn((url, options = {}) => {
      if (url.endsWith('/auth/session/'))
        return response({
          authenticated: true,
          user: { id: 'patient-user', email: 'patient@example.test' },
          roles: ['patient'],
        })
      if (url.endsWith('/auth/csrf/')) return response({ csrf_token: 'test' })
      if (url.endsWith('/public/hospital/')) return response({ display_name: 'Hospital Pilot' })
      if (url.endsWith('/queues/queue-1/snapshot/'))
        return response({
          queue_id: 'queue-1',
          ticket_id: 'ticket-1',
          token: 'A17',
          state: left ? 'cancelled' : 'waiting',
          current_served_token: 'A13',
          people_ahead: 3,
          wait_lower_minutes: 10,
          wait_upper_minutes: 20,
          doctor: { id: 'doctor-1', display_name: 'Dr. Farhana Islam' },
          location: { id: 'location-1', name: 'Outpatient Building' },
          chamber: { id: 'chamber-1', name: 'Room 203' },
        })
      if (url.endsWith('/queue-tickets/ticket-1/leave/') && options.method === 'POST') {
        left = true
        return response({
          ticket_id: 'ticket-1',
          queue_id: 'queue-1',
          token: 'A17',
          state: 'cancelled',
        })
      }
      return response([])
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<App />)
    const user = userEvent.setup()
    expect(await screen.findByRole('heading', { name: 'Where to go' })).toBeInTheDocument()
    expect(
      screen.getByText(/Dr\. Farhana Islam.*Outpatient Building.*Room 203/),
    ).toBeInTheDocument()
    await user.click(await screen.findByRole('button', { name: 'Leave queue' }))
    const dialog = screen.getByRole('dialog')
    const confirm = within(dialog).getByRole('button', { name: 'Leave queue' })
    expect(confirm).toBeDisabled()
    await user.type(within(dialog).getByLabelText(/Reason/i), 'Leaving hospital')
    await user.click(confirm)
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) => url.endsWith('/queue-tickets/ticket-1/leave/')),
      ).toBe(true),
    )
    const request = fetchMock.mock.calls.find(([url]) =>
      url.endsWith('/queue-tickets/ticket-1/leave/'),
    )
    expect(JSON.parse(request[1].body)).toEqual({ reason: 'Leaving hospital' })
  })
})
