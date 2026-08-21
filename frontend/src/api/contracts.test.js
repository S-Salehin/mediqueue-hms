import { describe, expect, it } from 'vitest'
import {
  API_ROUTES,
  activeQueueTicket,
  adminResourceBody,
  consentDecisionBody,
  patientRegistrationBody,
  paymentActionBody,
  scheduleBody,
  staffInvitationAcceptBody,
  patientClaimAcceptBody,
  patientClaimInvitationBody,
  rescheduleBody,
  receptionAppointmentsPath,
  latestConsentDecisions,
  assistedConsentBody,
  hospitalSettingsBody,
  mfaReplacementStartBody,
  patientCorrectionBody,
  reasonBody,
} from './contracts'
import { listPayload } from './client'

describe('frontend API contracts', () => {
  it('preserves possible patient matches for duplicate review', () => {
    const matches = [{ id: 'patient-1', mrn: 'MRN-000001' }]
    expect(listPayload({ data: { possible_matches: matches } })).toEqual(matches)
  })

  it('uses the canonical notification outbox route', () => {
    expect(API_ROUTES.notificationOutbox).toBe('/admin/notification-outbox/')
  })

  it('builds registration without UI-only confirmation fields', () => {
    expect(
      patientRegistrationBody(
        {
          email: ' patient@example.test ',
          password: 'a secure passphrase',
          password_confirm: 'ignored',
          full_name: ' Patient One ',
          phone: ' +8801700000000 ',
          date_of_birth: '1990-01-02',
          sex: 'unspecified',
          address: ' Dhaka ',
          privacy_accepted: true,
        },
        'notice-1',
      ),
    ).toEqual({
      email: 'patient@example.test',
      password: 'a secure passphrase',
      full_name: 'Patient One',
      phone: '+8801700000000',
      date_of_birth: '1990-01-02',
      sex: 'unspecified',
      address: 'Dhaka',
      privacy_notice_id: 'notice-1',
      privacy_accepted: true,
    })
  })

  it('uses canonical consent and payment field names', () => {
    expect(consentDecisionBody('notice-2', 'email_notifications', false)).toEqual({
      notice_version_id: 'notice-2',
      purpose: 'email_notifications',
      decision: false,
    })
    expect(paymentActionBody('paid_on_site', { reference: ' R-17 ' })).toEqual({
      state: 'paid_on_site',
      reference: 'R-17',
    })
    expect(
      paymentActionBody('refunded', {
        amountMinor: '1250',
        reason: ' Approved correction ',
        reference: ' ',
      }),
    ).toEqual({
      state: 'refunded',
      amount_minor: 1250,
      reason: 'Approved correction',
    })
    expect(paymentActionBody('unpaid')).toEqual({ state: 'unpaid' })
  })

  it('builds a schedule with backend identifiers and local-time fields', () => {
    expect(
      scheduleBody(
        {
          doctor: 'doctor-1',
          location: 'location-1',
          chamber: 'chamber-1',
          weekday: '2',
          start_local: '09:00',
          end_local: '13:00',
          slot_duration_minutes: '20',
          capacity_per_slot: '2',
          effective_from: '2026-08-15',
          effective_to: '',
        },
        'hospital-1',
      ),
    ).toEqual({
      hospital: 'hospital-1',
      doctor: 'doctor-1',
      location: 'location-1',
      chamber: 'chamber-1',
      weekday: 2,
      start_local: '09:00',
      end_local: '13:00',
      slot_duration_minutes: 20,
      capacity_per_slot: 2,
      effective_from: '2026-08-15',
      effective_to: null,
    })
    expect(
      scheduleBody(
        {
          doctor: 'doctor-1',
          location: 'location-1',
          chamber: 'chamber-1',
          weekday: 2,
          start_local: '09:00',
          end_local: '13:00',
          slot_duration_minutes: 20,
          capacity_per_slot: 2,
          effective_from: '2026-08-15',
          effective_to: '2026-12-31',
        },
        'hospital-1',
        true,
      ),
    ).not.toHaveProperty('hospital')
  })

  it('adds hospital ownership only when creating an admin resource', () => {
    expect(
      adminResourceBody('locations', { name: 'Main', address: 'Dhaka' }, 'hospital-1'),
    ).toEqual({
      name: 'Main',
      address: 'Dhaka',
      hospital: 'hospital-1',
    })
    expect(adminResourceBody('locations', { name: 'Main' }, 'hospital-1', true)).toEqual({
      name: 'Main',
    })
    expect(
      adminResourceBody('departments', { name: 'Medicine', display_order: '3' }, 'hospital-1'),
    ).toEqual({ name: 'Medicine', display_order: 3, hospital: 'hospital-1' })
    expect(
      adminResourceBody(
        'doctors',
        { user: 'user-1', consultation_fee_minor: '', department_ids: undefined },
        'hospital-1',
      ),
    ).toEqual({
      user: 'user-1',
      consultation_fee_minor: 0,
      department_ids: [],
      hospital: 'hospital-1',
    })
  })

  it('derives the active queue ticket from active_ticket_id without exposing another record', () => {
    const active = { id: 'ticket-2', token: 'A002' }
    expect(
      activeQueueTicket({ active_ticket_id: 'ticket-2', tickets: [{ id: 'ticket-1' }, active] }),
    ).toBe(active)
    expect(activeQueueTicket({ active_ticket_id: null, tickets: [{ id: 'ticket-1' }] })).toBeNull()
    expect(activeQueueTicket({ current_ticket: active, tickets: [] })).toBe(active)
    expect(activeQueueTicket({ current: active, waiting_tickets: [] })).toBe(active)
  })

  it('builds staff invitation acceptance and patient claim bodies without confirmation fields', () => {
    expect(staffInvitationAcceptBody('token', ' Doctor One ', 'secure phrase')).toEqual({
      token: 'token',
      display_name: 'Doctor One',
      password: 'secure phrase',
    })
    expect(patientClaimAcceptBody('claim-token', 'secure phrase')).toEqual({
      token: 'claim-token',
      password: 'secure phrase',
    })
    expect(patientClaimInvitationBody(' patient@example.test ')).toEqual({
      email: 'patient@example.test',
    })
  })

  it('builds the canonical reschedule action body', () => {
    expect(
      rescheduleBody(
        { schedule_id: 'schedule-1', start_at: '2026-08-18T09:00:00Z' },
        'department-1',
        ' Better time ',
      ),
    ).toEqual({
      schedule_id: 'schedule-1',
      department_id: 'department-1',
      start_at: '2026-08-18T09:00:00Z',
      reason: 'Better time',
    })
    expect(
      rescheduleBody(
        { schedule_id: 'schedule-1', start_at: '2026-08-18T09:00:00Z' },
        'department-1',
      ),
    ).toEqual({
      schedule_id: 'schedule-1',
      department_id: 'department-1',
      start_at: '2026-08-18T09:00:00Z',
    })
  })

  it('builds a bounded reception appointment search path', () => {
    expect(receptionAppointmentsPath('2026-08-18', ' MRN-100 ')).toBe(
      '/appointments/?date=2026-08-18&q=MRN-100',
    )
    expect(receptionAppointmentsPath('', '')).toBe('/appointments/')
  })

  it('uses the latest recorded consent decision regardless of response order', () => {
    expect(
      latestConsentDecisions([
        { purpose: 'email_notifications', decision: false, created_at: '2026-08-15T09:00:00Z' },
        { purpose: 'email_notifications', decision: true, created_at: '2026-08-14T09:00:00Z' },
      ]),
    ).toEqual({ email_notifications: false })
  })

  it('maps hospital settings to the strict Bangladesh pilot contract', () => {
    expect(
      hospitalSettingsBody({
        id: 'ignored',
        display_name: ' Hospital Pilot ',
        short_name: ' HP ',
        tagline: ' Clear care ',
        logo_url: ' https://hospital.example/logo.svg ',
        email: ' contact@example.test ',
        phone: ' +8801700000000 ',
        address: ' Dhaka ',
        timezone: 'UTC',
        currency: 'USD',
        default_slot_duration_minutes: '25',
        late_arrival_minutes: 0,
        patient_cancellation_cutoff_minutes: '90',
        operational_settings: { secret: true },
      }),
    ).toEqual({
      display_name: 'Hospital Pilot',
      short_name: 'HP',
      tagline: 'Clear care',
      logo_url: 'https://hospital.example/logo.svg',
      email: 'contact@example.test',
      phone: '+8801700000000',
      address: 'Dhaka',
      timezone: 'Asia/Dhaka',
      currency: 'BDT',
      default_slot_duration_minutes: 25,
      late_arrival_minutes: 0,
      patient_cancellation_cutoff_minutes: 90,
    })
    expect(hospitalSettingsBody({ name: 'Fallback hospital' })).toMatchObject({
      display_name: 'Fallback hospital',
      default_slot_duration_minutes: 20,
      late_arrival_minutes: 15,
      patient_cancellation_cutoff_minutes: 0,
    })
  })

  it('builds reasoned correction, consent, and MFA replacement bodies', () => {
    expect(mfaReplacementStartBody('current password')).toEqual({
      current_password: 'current password',
    })
    expect(reasonBody(' Operational correction ')).toEqual({ reason: 'Operational correction' })
    expect(assistedConsentBody('notice-1', 'email_notifications', 0)).toEqual({
      notice_version_id: 'notice-1',
      purpose: 'email_notifications',
      decision: false,
    })
    expect(
      patientCorrectionBody({
        full_name: ' Patient One ',
        email: ' patient@example.test ',
        phone: ' +8801700000000 ',
        date_of_birth: '1990-01-01',
        sex: 'unspecified',
        address: ' Dhaka ',
        reason: ' Typo ',
      }),
    ).toEqual({
      full_name: 'Patient One',
      email: 'patient@example.test',
      phone: '+8801700000000',
      date_of_birth: '1990-01-01',
      sex: 'unspecified',
      address: 'Dhaka',
      reason: 'Typo',
    })
  })
})
