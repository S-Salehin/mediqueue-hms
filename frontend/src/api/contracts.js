export const API_ROUTES = Object.freeze({
  notificationOutbox: '/admin/notification-outbox/',
})

export const HOSPITAL_TIMEZONE = 'Asia/Dhaka'
export const HOSPITAL_CURRENCY = 'BDT'

export function patientRegistrationBody(values, privacyNoticeId) {
  return {
    email: values.email.trim(),
    password: values.password,
    full_name: values.full_name.trim(),
    phone: values.phone.trim(),
    date_of_birth: values.date_of_birth,
    sex: values.sex,
    address: values.address.trim(),
    privacy_notice_id: privacyNoticeId,
    privacy_accepted: Boolean(values.privacy_accepted),
  }
}

export function consentDecisionBody(noticeVersionId, purpose, decision) {
  return { notice_version_id: noticeVersionId, purpose, decision }
}

export function paymentActionBody(state, { amountMinor, reason, reference } = {}) {
  return {
    state,
    ...(amountMinor !== undefined && amountMinor !== ''
      ? { amount_minor: Number(amountMinor) }
      : {}),
    ...(reason?.trim() ? { reason: reason.trim() } : {}),
    ...(reference?.trim() ? { reference: reference.trim() } : {}),
  }
}

export function scheduleBody(values, hospitalId, editing = false) {
  return {
    ...(!editing ? { hospital: hospitalId } : {}),
    doctor: values.doctor,
    location: values.location,
    chamber: values.chamber,
    weekday: Number(values.weekday),
    start_local: values.start_local,
    end_local: values.end_local,
    slot_duration_minutes: Number(values.slot_duration_minutes),
    capacity_per_slot: Number(values.capacity_per_slot),
    effective_from: values.effective_from,
    effective_to: values.effective_to || null,
  }
}

export function hospitalSettingsBody(values = {}) {
  return {
    display_name: String(values.display_name || values.name || '').trim(),
    short_name: String(values.short_name || '').trim(),
    logo_url: String(values.logo_url || '').trim(),
    tagline: String(values.tagline || '').trim(),
    email: String(values.email || '').trim(),
    phone: String(values.phone || '').trim(),
    address: String(values.address || '').trim(),
    timezone: HOSPITAL_TIMEZONE,
    currency: HOSPITAL_CURRENCY,
    default_slot_duration_minutes: Number(values.default_slot_duration_minutes || 20),
    late_arrival_minutes: Number(values.late_arrival_minutes ?? 15),
    patient_cancellation_cutoff_minutes: Number(values.patient_cancellation_cutoff_minutes ?? 0),
  }
}

export function mfaReplacementStartBody(currentPassword) {
  return { current_password: currentPassword }
}

export function reasonBody(reason) {
  return { reason: String(reason || '').trim() }
}

export function patientCorrectionBody(values) {
  return {
    full_name: values.full_name.trim(),
    email: values.email.trim(),
    phone: values.phone.trim(),
    date_of_birth: values.date_of_birth,
    sex: values.sex,
    address: values.address.trim(),
    reason: values.reason.trim(),
  }
}

export function assistedConsentBody(noticeVersionId, purpose, decision) {
  return {
    notice_version_id: noticeVersionId,
    purpose,
    decision: Boolean(decision),
  }
}

export function adminResourceBody(type, values, hospitalId, editing = false) {
  const body = { ...values }
  if (!editing) body.hospital = hospitalId
  if (type === 'doctors') {
    body.consultation_fee_minor = Number(body.consultation_fee_minor || 0)
    body.department_ids = Array.isArray(body.department_ids) ? body.department_ids : []
  }
  if (type === 'departments') body.display_order = Number(body.display_order || 0)
  return body
}

export function activeQueueTicket(snapshot) {
  const tickets = snapshot?.tickets || snapshot?.waiting_tickets || []
  return (
    snapshot?.current_ticket ||
    snapshot?.current ||
    tickets.find((ticket) => String(ticket.id) === String(snapshot?.active_ticket_id)) ||
    null
  )
}

export function staffInvitationAcceptBody(token, displayName, password) {
  return { token, display_name: displayName.trim(), password }
}

export function patientClaimAcceptBody(token, password) {
  return { token, password }
}

export function patientClaimInvitationBody(email) {
  return { email: email.trim() }
}

export function rescheduleBody(slot, departmentId, reason = '') {
  return {
    schedule_id: slot.schedule_id,
    department_id: departmentId,
    start_at: slot.start_at,
    ...(reason.trim() ? { reason: reason.trim() } : {}),
  }
}

export function receptionAppointmentsPath(date, search = '') {
  const params = new URLSearchParams()
  if (date) params.set('date', date)
  if (search.trim()) params.set('q', search.trim())
  const query = params.toString()
  return `/appointments/${query ? `?${query}` : ''}`
}

export function latestConsentDecisions(records = []) {
  return [...records]
    .sort((left, right) => new Date(left.created_at || 0) - new Date(right.created_at || 0))
    .reduce((decisions, record) => {
      const purpose = record.purpose || record.consent_type
      if (purpose) decisions[purpose] = record.decision ?? record.granted ?? record.value
      return decisions
    }, {})
}
