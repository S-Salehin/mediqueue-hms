import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import {
  ArrowLeft,
  ArrowRight,
  Bell,
  CalendarCheck2,
  CalendarClock,
  CheckCircle2,
  ChevronRight,
  CircleUserRound,
  Clock3,
  CreditCard,
  FileCheck2,
  Inbox,
  MapPin,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  TicketCheck,
  UserRound,
  UsersRound,
} from 'lucide-react'
import { apiRequest, listPayload, payload, queryString } from '../api/client'
import { consentDecisionBody, latestConsentDecisions, rescheduleBody } from '../api/contracts'
import { useAuth } from '../context/AuthContext'
import { useBrand } from '../context/BrandContext'
import { useQueuePolling } from '../hooks/useQueuePolling'
import { useResource } from '../hooks/useResource'
import {
  departmentName,
  doctorName,
  formatDate,
  formatDateTime,
  formatTime,
  hospitalDateInputValue,
  money,
  tokenLabel,
} from '../utils/format'
import { queueArrivalGuidance } from '../utils/queue'
import {
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  ErrorNotice,
  ErrorSummary,
  Field,
  LoadingState,
  MetricCard,
  OfflineNotice,
  PageHeader,
  StatusBadge,
  SuccessNotice,
  Table,
} from '../components/ui'

export function PatientDashboard() {
  const { user } = useAuth()
  const { data, loading, error, reload } = useResource('/dashboards/patient/')
  if (loading) return <LoadingState label="Loading your dashboard" />
  if (error) return <ErrorNotice error={error} onRetry={reload} />
  const summary = data?.summary || {}
  const recent = data?.recent || data?.appointments || []
  const next = data?.next_appointment || recent.find((item) => item.status === 'confirmed')
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Patient dashboard"
        title={`Hello${user?.first_name || user?.display_name ? `, ${user.first_name || user.display_name.split(' ')[0]}` : ''}`}
        description="Here is what is happening with your hospital visits."
        actions={
          <Link className="button button-primary button-md" to="/patient/appointments/new">
            <CalendarCheck2 />
            Book appointment
          </Link>
        }
      />
      <div className="metric-grid">
        <MetricCard
          icon={CalendarClock}
          label="Upcoming"
          value={summary.upcoming_appointments ?? summary.upcoming ?? summary.confirmed ?? '0'}
          detail="Confirmed visits"
        />
        <MetricCard
          icon={CheckCircle2}
          label="Completed"
          value={summary.completed ?? '0'}
          detail="Previous visits"
          tone="green"
        />
        <MetricCard
          icon={Bell}
          label="Unread updates"
          value={summary.unread_notifications ?? '0'}
          detail="Your messages"
          tone="violet"
        />
      </div>
      {next ? (
        <Card className="next-visit-card">
          <div className="next-visit-head">
            <div>
              <p className="eyebrow">Next appointment</p>
              <h2>{doctorName(next.doctor)}</h2>
              <p>{departmentName(next.department)}</p>
            </div>
            <StatusBadge status={next.status} />
          </div>
          <div className="visit-facts">
            <span>
              <CalendarCheck2 />
              {formatDate(next.start_at || next.date)}
            </span>
            <span>
              <Clock3 />
              {formatTime(next.start_at || next.time)}
            </span>
            {next.location ? (
              <span>
                <MapPin />
                {departmentName(next.location)}
              </span>
            ) : null}
          </div>
          <div className="card-actions">
            <Link
              className="button button-secondary button-md"
              to={`/patient/appointments/${next.id}`}
            >
              View details
            </Link>
            {next.queue?.queue_id || next.queue_id ? (
              <Link
                className="button button-primary button-md"
                to={`/patient/queue/${next.queue?.queue_id || next.queue_id}`}
              >
                Open queue status
              </Link>
            ) : null}
          </div>
        </Card>
      ) : (
        <Card>
          <EmptyState
            icon={CalendarCheck2}
            title="No upcoming appointment"
            description="Find a doctor and choose an available hospital time when you are ready."
            action={
              <Link className="button button-primary button-md" to="/patient/appointments/new">
                Book an appointment
              </Link>
            }
          />
        </Card>
      )}
      <Card>
        <div className="card-heading">
          <div>
            <h2>Recent appointments</h2>
            <p>Your latest confirmed and completed visits.</p>
          </div>
          <Link className="text-arrow" to="/patient/appointments">
            View all <ArrowRight />
          </Link>
        </div>
        {recent.length ? (
          <AppointmentTable items={recent.slice(0, 5)} />
        ) : (
          <EmptyState
            title="No appointment history"
            description="Your appointments will appear here after booking."
          />
        )}
      </Card>
    </div>
  )
}

export function PatientAppointmentsPage() {
  const [status, setStatus] = useState('')
  const { data, loading, error, reload } = useResource(`/appointments/${queryString({ status })}`, {
    list: true,
  })
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="My appointments"
        title="Appointments"
        description="Review your own upcoming and previous hospital visits."
        actions={
          <Link className="button button-primary button-md" to="/patient/appointments/new">
            <CalendarCheck2 />
            Book appointment
          </Link>
        }
      />
      <Card className="filter-row">
        <Field label="Filter by status" id="appointment-filter">
          {(props) => (
            <select {...props} value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">All appointments</option>
              <option value="confirmed">Confirmed</option>
              <option value="completed">Completed</option>
              <option value="cancelled">Cancelled</option>
              <option value="no_show">No show</option>
            </select>
          )}
        </Field>
      </Card>
      {loading ? (
        <LoadingState label="Loading appointments" />
      ) : error ? (
        <ErrorNotice error={error} onRetry={reload} />
      ) : data.length ? (
        <Card>
          <AppointmentTable items={data} />
        </Card>
      ) : (
        <Card>
          <EmptyState
            icon={CalendarCheck2}
            title="No appointments in this view"
            description="Change the filter or book an available visit."
          />
        </Card>
      )}
    </div>
  )
}

function AppointmentTable({ items }) {
  return (
    <Table caption="Appointments" columns={['Date and time', 'Doctor', 'Location', 'Status', '']}>
      {items.map((appointment) => (
        <tr key={appointment.id}>
          <td data-label="Date and time">
            <strong>{formatDate(appointment.start_at || appointment.date)}</strong>
            <small>{formatTime(appointment.start_at || appointment.time)}</small>
          </td>
          <td data-label="Doctor">
            <strong>{doctorName(appointment.doctor)}</strong>
            <small>{departmentName(appointment.department)}</small>
          </td>
          <td data-label="Location">
            <strong>{departmentName(appointment.location)}</strong>
            <small>{departmentName(appointment.chamber)}</small>
          </td>
          <td data-label="Status">
            <StatusBadge status={appointment.status} />
          </td>
          <td>
            <Link
              className="table-action"
              aria-label={`View appointment with ${doctorName(appointment.doctor)}`}
              to={`/patient/appointments/${appointment.id}`}
            >
              View <ChevronRight />
            </Link>
          </td>
        </tr>
      ))}
    </Table>
  )
}

export function BookingPage() {
  const navigate = useNavigate()
  const [search] = useSearchParams()
  const [step, setStep] = useState(1)
  const [doctors, setDoctors] = useState([])
  const [departments, setDepartments] = useState([])
  const [slots, setSlots] = useState([])
  const [loading, setLoading] = useState(true)
  const [slotsLoading, setSlotsLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [values, setValues] = useState({
    department_id: '',
    doctor_id: search.get('doctor') || '',
    date: search.get('date') || hospitalDateInputValue(),
    slot_id: search.get('slot') || '',
  })
  useEffect(() => {
    Promise.all([apiRequest('/public/doctors/'), apiRequest('/public/departments/')])
      .then(([doctorResult, departmentResult]) => {
        setDoctors(listPayload(doctorResult))
        setDepartments(listPayload(departmentResult))
      })
      .catch(setError)
      .finally(() => setLoading(false))
  }, [])
  useEffect(() => {
    if (!values.doctor_id || !values.date) {
      setSlots([])
      return
    }
    let current = true
    setSlots([])
    setSlotsLoading(true)
    setError(null)
    apiRequest(
      `/public/doctors/${values.doctor_id}/availability/${queryString({ date_from: values.date, date_to: values.date })}`,
    )
      .then((result) => {
        if (current) setSlots(listPayload(result))
      })
      .catch((requestError) => {
        if (current) setError(requestError)
      })
      .finally(() => {
        if (current) setSlotsLoading(false)
      })
    return () => {
      current = false
    }
  }, [values.doctor_id, values.date])
  const filteredDoctors = values.department_id
    ? doctors.filter((doctor) =>
        (doctor.departments || [doctor.department]).some(
          (department) => String(department?.id || department) === values.department_id,
        ),
      )
    : doctors
  const doctor = doctors.find((item) => String(item.id) === values.doctor_id)
  const slot = slots.find((item) => String(item.start_at) === values.slot_id)
  const stepValid = step === 1 ? values.doctor_id : step === 2 ? Boolean(values.date && slot) : true
  const change = (key) => (event) =>
    setValues((current) => ({
      ...current,
      [key]: event.target.value,
      ...(key === 'department_id' ? { doctor_id: '', slot_id: '' } : {}),
      ...(key === 'doctor_id' || key === 'date' ? { slot_id: '' } : {}),
    }))
  const confirm = async () => {
    if (!slot || !doctor) {
      setError(new Error('Choose an available doctor, date, and time before confirming.'))
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      const body = {
        schedule_id: slot?.schedule_id,
        department_id:
          values.department_id || doctor?.departments?.[0]?.id || doctor?.department?.id,
        start_at: slot?.start_at,
      }
      const created = payload(await apiRequest('/appointments/', { method: 'POST', body }))
      navigate(`/patient/appointments/${created.id}`, {
        replace: true,
        state: { booked: true },
      })
    } catch (requestError) {
      setError(requestError)
      const fields = requestError.fieldErrors || {}
      if (fields.doctor_id || fields.department_id) setStep(1)
      if (fields.schedule_id || fields.start_at || fields.slot_id) setStep(2)
    } finally {
      setSubmitting(false)
    }
  }
  if (loading) return <LoadingState label="Preparing appointment booking" />
  return (
    <div className="page-stack booking-page">
      <Link className="back-link" to="/patient/appointments">
        <ArrowLeft />
        Back to appointments
      </Link>
      <PageHeader
        eyebrow="New appointment"
        title="Book an appointment"
        description="Choose from the active hospital schedule, then review before confirming."
      />
      <ol className="stepper" aria-label="Booking progress">
        {['Doctor', 'Date and time', 'Review'].map((label, index) => (
          <li
            className={step === index + 1 ? 'active' : step > index + 1 ? 'complete' : ''}
            key={label}
          >
            <span>{step > index + 1 ? <CheckCircle2 /> : index + 1}</span>
            <strong>{label}</strong>
          </li>
        ))}
      </ol>
      <ErrorSummary
        errors={error?.fieldErrors}
        fieldIds={{
          department_id: 'booking-department',
          doctor_id: 'booking-doctor',
          date: 'booking-date',
          schedule_id: 'booking-time',
          slot_id: 'booking-time',
          start_at: 'booking-time',
        }}
      />
      {error && !Object.keys(error.fieldErrors || {}).length ? <ErrorNotice error={error} /> : null}
      <Card className="booking-card">
        {step === 1 ? (
          <div>
            <div className="card-heading">
              <div>
                <h2>Choose a doctor</h2>
                <p>Only active hospital profiles appear.</p>
              </div>
            </div>
            <Field label="Department" id="booking-department">
              {(props) => (
                <select {...props} value={values.department_id} onChange={change('department_id')}>
                  <option value="">All departments</option>
                  {departments.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              )}
            </Field>
            {filteredDoctors.length ? (
              <div
                id="booking-doctor"
                className="choice-grid"
                role="radiogroup"
                aria-label="Doctors"
                tabIndex="-1"
              >
                {filteredDoctors.map((item) => (
                  <label
                    className={`choice-card ${values.doctor_id === String(item.id) ? 'selected' : ''}`}
                    key={item.id}
                  >
                    <input
                      type="radio"
                      name="doctor"
                      value={item.id}
                      checked={values.doctor_id === String(item.id)}
                      onChange={change('doctor_id')}
                    />
                    <span className="doctor-avatar" aria-hidden="true">
                      DR
                    </span>
                    <span>
                      <strong>{doctorName(item)}</strong>
                      <small>{departmentName(item.departments || item.department)}</small>
                      {item.designation ? <small>{item.designation}</small> : null}
                    </span>
                    <span className="radio-mark" />
                  </label>
                ))}
              </div>
            ) : (
              <EmptyState
                icon={Stethoscope}
                title="No doctors in this department"
                description="Choose another department."
              />
            )}
          </div>
        ) : null}
        {step === 2 ? (
          <div>
            <div className="card-heading">
              <div>
                <h2>Choose a date and time</h2>
                <p>{doctorName(doctor)}</p>
              </div>
            </div>
            <Field label="Appointment date" id="booking-date">
              {(props) => (
                <input
                  {...props}
                  type="date"
                  min={hospitalDateInputValue()}
                  value={values.date}
                  onChange={change('date')}
                />
              )}
            </Field>
            {slotsLoading ? (
              <LoadingState label="Checking open times" />
            ) : slots.length ? (
              <div
                id="booking-time"
                className="time-grid"
                role="radiogroup"
                aria-label="Available appointment times"
                tabIndex="-1"
              >
                {slots.map((item) => {
                  const value = String(item.start_at)
                  return (
                    <label className={values.slot_id === value ? 'selected' : ''} key={value}>
                      <input
                        type="radio"
                        name="slot"
                        value={value}
                        checked={values.slot_id === value}
                        onChange={change('slot_id')}
                      />
                      <Clock3 />
                      <strong>{formatTime(item.display_start || item.start_at)}</strong>
                      {item.available_capacity !== undefined ? (
                        <small>{item.available_capacity} left</small>
                      ) : null}
                    </label>
                  )
                })}
              </div>
            ) : (
              <EmptyState
                icon={CalendarClock}
                title="No open times on this date"
                description="Try another date. Availability can change until you confirm."
              />
            )}
          </div>
        ) : null}
        {step === 3 ? (
          <div className="review-step">
            <div className="card-heading">
              <div>
                <h2>Review the appointment</h2>
                <p>Check these details before confirming.</p>
              </div>
            </div>
            <dl className="review-list">
              <div>
                <dt>Doctor</dt>
                <dd>{doctorName(doctor)}</dd>
              </div>
              <div>
                <dt>Department</dt>
                <dd>{departmentName(doctor?.departments || doctor?.department)}</dd>
              </div>
              <div>
                <dt>Date</dt>
                <dd>{formatDate(values.date)}</dd>
              </div>
              <div>
                <dt>Time</dt>
                <dd>{formatTime(slot?.display_start || slot?.start_at)}</dd>
              </div>
              {doctor?.consultation_fee_minor !== undefined ? (
                <div>
                  <dt>Visit fee</dt>
                  <dd>{money(doctor.consultation_fee_minor)}</dd>
                </div>
              ) : null}
            </dl>
            <div className="notice notice-info">
              <ShieldCheck />
              <p>
                A queue token is not assigned during booking. Reception issues the final token when
                you arrive and check in.
              </p>
            </div>
          </div>
        ) : null}
        <div className="booking-actions">
          {step > 1 ? (
            <Button variant="secondary" onClick={() => setStep((value) => value - 1)}>
              <ArrowLeft />
              Back
            </Button>
          ) : (
            <span />
          )}
          {step < 3 ? (
            <Button disabled={!stepValid} onClick={() => setStep((value) => value + 1)}>
              Continue <ArrowRight />
            </Button>
          ) : (
            <Button loading={submitting} onClick={confirm}>
              <CalendarCheck2 />
              Confirm appointment
            </Button>
          )}
        </div>
      </Card>
    </div>
  )
}

export function AppointmentDetailPage() {
  const { appointmentId } = useParams()
  const { state } = useLocation()
  const {
    data: appointment,
    loading,
    error,
    reload,
  } = useResource(`/appointments/${appointmentId}/`)
  const {
    data: payment,
    loading: paymentLoading,
    error: paymentError,
  } = useResource(`/appointments/${appointmentId}/payment/`, { enabled: Boolean(appointmentId) })
  const [dialog, setDialog] = useState(false)
  const [reason, setReason] = useState('')
  const [actionError, setActionError] = useState(null)
  const [acting, setActing] = useState(false)
  const cancel = async () => {
    setActing(true)
    setActionError(null)
    try {
      await apiRequest(`/appointments/${appointmentId}/cancel/`, {
        method: 'POST',
        body: { reason: reason || 'Cancelled by patient' },
      })
      setDialog(false)
      reload()
    } catch (requestError) {
      setActionError(requestError)
    } finally {
      setActing(false)
    }
  }
  if (loading) return <LoadingState label="Loading appointment" />
  if (error) return <ErrorNotice error={error} onRetry={reload} />
  const queueId =
    appointment?.queue?.queue_id ||
    appointment?.queue?.session ||
    appointment?.queue_id ||
    appointment?.queue_ticket?.session ||
    appointment?.queue_ticket?.queue_id
  return (
    <div className="page-stack">
      <Link className="back-link" to="/patient/appointments">
        <ArrowLeft />
        Back to appointments
      </Link>
      {state?.booked ? <SuccessNotice>Your appointment was confirmed.</SuccessNotice> : null}
      <PageHeader
        eyebrow="Appointment details"
        title={doctorName(appointment.doctor)}
        description={departmentName(appointment.department)}
        actions={<StatusBadge status={appointment.status} />}
      />
      <div className="detail-grid">
        <Card>
          <h2>Visit information</h2>
          <dl className="detail-list">
            <div>
              <dt>Date and time</dt>
              <dd>{formatDateTime(appointment.start_at)}</dd>
            </div>
            <div>
              <dt>Location</dt>
              <dd>{departmentName(appointment.location)}</dd>
            </div>
            <div>
              <dt>Chamber</dt>
              <dd>{departmentName(appointment.chamber)}</dd>
            </div>
            <div>
              <dt>Reference</dt>
              <dd>{appointment.reference || 'Available through hospital support'}</dd>
            </div>
          </dl>
          {appointment.status === 'confirmed' ? (
            <div className="card-actions">
              {!queueId ? (
                <>
                  <Link
                    className="button button-secondary button-md"
                    to={`/patient/appointments/${appointment.id}/reschedule`}
                  >
                    Reschedule
                  </Link>
                  <Button variant="danger-soft" onClick={() => setDialog(true)}>
                    Cancel appointment
                  </Button>
                </>
              ) : null}
              {queueId ? (
                <Link className="button button-primary button-md" to={`/patient/queue/${queueId}`}>
                  Open live queue <ArrowRight />
                </Link>
              ) : null}
            </div>
          ) : null}
        </Card>
        <Card>
          <h2>Payment summary</h2>
          {paymentLoading ? (
            <LoadingState label="Loading payment summary" />
          ) : paymentError ? (
            <ErrorNotice error={paymentError} />
          ) : payment ? (
            <dl className="detail-list">
              <div>
                <dt>Status</dt>
                <dd>
                  <StatusBadge status={payment.state || appointment.payment_state} />
                </dd>
              </div>
              {payment.amount_minor !== undefined ? (
                <div>
                  <dt>Amount</dt>
                  <dd>{money(payment.amount_minor, payment.currency)}</dd>
                </div>
              ) : null}
              <div>
                <dt>Collection</dt>
                <dd>Onsite only</dd>
              </div>
            </dl>
          ) : (
            <p>Payment information is not available yet.</p>
          )}
          <p className="helper-text">This service does not process cards or store card details.</p>
        </Card>
      </div>
      <Card className="instruction-card">
        <TicketCheck />
        <div>
          <h2>On arrival</h2>
          <p>
            Report to reception for check-in. Your final queue token is issued only after staff
            confirm your arrival.
          </p>
        </div>
      </Card>
      <ConfirmDialog
        open={dialog}
        title="Cancel this appointment?"
        description="A cancelled appointment cannot be reopened. You can book another available time later."
        confirmLabel="Cancel appointment"
        danger
        loading={acting}
        onConfirm={cancel}
        onClose={() => setDialog(false)}
      >
        {actionError ? <ErrorNotice error={actionError} /> : null}
        <Field
          label="Reason"
          id="cancel-reason"
          hint="A short operational reason helps the hospital audit corrections."
        >
          {(props) => (
            <textarea
              {...props}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              maxLength="200"
            />
          )}
        </Field>
      </ConfirmDialog>
    </div>
  )
}

export function RescheduleAppointmentPage({ backTo, completeTo }) {
  const { appointmentId } = useParams()
  const navigate = useNavigate()
  const {
    data: appointment,
    loading,
    error,
    reload,
  } = useResource(`/appointments/${appointmentId}/`)
  const [date, setDate] = useState(hospitalDateInputValue)
  const [slots, setSlots] = useState([])
  const [selected, setSelected] = useState('')
  const [reason, setReason] = useState('')
  const [slotsLoading, setSlotsLoading] = useState(false)
  const [actionError, setActionError] = useState(null)
  const [saving, setSaving] = useState(false)
  const doctorId = appointment?.doctor?.id
  const departmentId = appointment?.department?.id || appointment?.department

  useEffect(() => {
    if (!doctorId || !date || appointment?.status !== 'confirmed') return undefined
    let current = true
    setSlots([])
    setSlotsLoading(true)
    setSelected('')
    setActionError(null)
    apiRequest(
      `/public/doctors/${doctorId}/availability/${queryString({ date_from: date, date_to: date })}`,
    )
      .then((result) => {
        if (current) setSlots(listPayload(result))
      })
      .catch((requestError) => {
        if (current) setActionError(requestError)
      })
      .finally(() => {
        if (current) setSlotsLoading(false)
      })
    return () => {
      current = false
    }
  }, [appointment?.status, date, doctorId])

  const submit = async (event) => {
    event.preventDefault()
    const slot = slots.find((item) => String(item.start_at) === selected)
    if (!slot) return
    setSaving(true)
    setActionError(null)
    try {
      await apiRequest(`/appointments/${appointmentId}/reschedule/`, {
        method: 'POST',
        body: rescheduleBody(slot, departmentId, reason),
      })
      navigate(completeTo || `/patient/appointments/${appointmentId}`, { replace: true })
    } catch (requestError) {
      setActionError(requestError)
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <LoadingState label="Loading appointment" />
  if (error) return <ErrorNotice error={error} onRetry={reload} />
  if (appointment.status !== 'confirmed') {
    return (
      <div className="page-stack">
        <Link className="back-link" to={backTo || `/patient/appointments/${appointmentId}`}>
          <ArrowLeft />
          Back to appointments
        </Link>
        <Card>
          <EmptyState
            title="This appointment cannot be rescheduled"
            description="Only confirmed appointments can move to another available time."
          />
        </Card>
      </div>
    )
  }
  return (
    <div className="page-stack">
      <Link className="back-link" to={backTo || `/patient/appointments/${appointmentId}`}>
        <ArrowLeft />
        Back to appointments
      </Link>
      <PageHeader
        eyebrow="Appointment change"
        title="Choose another time"
        description={`Select an available time with ${doctorName(appointment.doctor)}.`}
      />
      <ErrorSummary
        errors={actionError?.fieldErrors}
        fieldIds={{
          date: 'reschedule-date',
          schedule_id: 'reschedule-time',
          start_at: 'reschedule-time',
          reason: 'reschedule-reason',
        }}
      />
      {actionError && !Object.keys(actionError.fieldErrors || {}).length ? (
        <ErrorNotice error={actionError} />
      ) : null}
      <Card className="form-card">
        <form onSubmit={submit}>
          <Field label="New appointment date" id="reschedule-date" required>
            {(props) => (
              <input
                {...props}
                type="date"
                min={hospitalDateInputValue()}
                value={date}
                onChange={(event) => setDate(event.target.value)}
                required
              />
            )}
          </Field>
          {slotsLoading ? (
            <LoadingState label="Checking open times" />
          ) : slots.length ? (
            <Field label="Available time" id="reschedule-time" required>
              {(props) => (
                <select
                  {...props}
                  value={selected}
                  onChange={(event) => setSelected(event.target.value)}
                  required
                >
                  <option value="">Select an open time</option>
                  {slots.map((slot) => (
                    <option key={slot.start_at} value={slot.start_at}>
                      {formatTime(slot.display_start || slot.start_at)}, {slot.available_capacity}{' '}
                      available
                    </option>
                  ))}
                </select>
              )}
            </Field>
          ) : (
            <EmptyState title="No open times on this date" description="Choose another date." />
          )}
          <Field label="Reason for change" id="reschedule-reason">
            {(props) => (
              <textarea
                {...props}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                maxLength="500"
              />
            )}
          </Field>
          <div className="form-actions">
            <Button type="submit" loading={saving} disabled={!selected}>
              Confirm new time
            </Button>
          </div>
        </form>
      </Card>
    </div>
  )
}

export function PatientQueuePage() {
  const { queueId } = useParams()
  const polling = useQueuePolling(queueId)
  const [leaveOpen, setLeaveOpen] = useState(false)
  const [leaveReason, setLeaveReason] = useState('')
  const [leaving, setLeaving] = useState(false)
  const [leaveError, setLeaveError] = useState(null)
  const { snapshot, loading, error, online, stale, lastSuccess, announcement, terminal } = polling
  if (loading && !snapshot) return <LoadingState label="Connecting to your queue" />
  if (error && !snapshot) return <ErrorNotice error={error} onRetry={polling.refresh} />
  const state = snapshot?.state || snapshot?.status
  const canLeave = ['waiting', 'called', 'deferred'].includes(state) && snapshot?.ticket_id
  const leaveQueue = async () => {
    setLeaving(true)
    setLeaveError(null)
    try {
      await apiRequest(`/queue-tickets/${snapshot.ticket_id}/leave/`, {
        method: 'POST',
        body: { reason: leaveReason.trim() },
      })
      setLeaveOpen(false)
      setLeaveReason('')
      await polling.refresh()
    } catch (requestError) {
      setLeaveError(requestError)
    } finally {
      setLeaving(false)
    }
  }
  const range = terminal
    ? 'Visit finished'
    : snapshot?.wait_lower_minutes !== undefined
      ? `${snapshot.wait_lower_minutes} to ${snapshot.wait_upper_minutes} min`
      : snapshot?.point_wait_minutes !== undefined
        ? `About ${snapshot.point_wait_minutes} min`
        : 'Updating'
  return (
    <div className="page-stack queue-page">
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {announcement}
      </div>
      <PageHeader
        eyebrow="Personal queue status"
        title="Your visit progress"
        description="This page shows tokens only. It never displays another patient’s name."
        actions={
          <>
            <Button variant="secondary" onClick={polling.refresh}>
              <RefreshCw />
              Refresh
            </Button>
            {canLeave ? (
              <Button
                variant="danger-soft"
                onClick={() => {
                  setLeaveOpen(true)
                  setLeaveError(null)
                }}
              >
                Leave queue
              </Button>
            ) : null}
          </>
        }
      />
      {!online || stale ? (
        <OfflineNotice
          offline={!online}
          stale={stale}
          lastUpdated={lastSuccess ? formatTime(lastSuccess) : null}
        />
      ) : null}
      {error && snapshot ? (
        <ErrorNotice error={error} title="The latest refresh did not finish" />
      ) : null}
      <Card className={`live-queue-card ${terminal ? 'queue-terminal' : ''}`}>
        <div className="queue-live-row">
          <span className={stale ? 'stale-pill' : 'live-pill'}>
            <span />
            {stale ? 'Delayed' : 'Live update'}
          </span>
          <span>Last checked {lastSuccess ? formatTime(lastSuccess) : 'not yet'}</span>
        </div>
        <div className="queue-token-grid">
          <div className="own-token">
            <small>Your token</small>
            <strong>{tokenLabel(snapshot?.token)}</strong>
            <StatusBadge status={state} />
          </div>
          <div>
            <small>Currently serving</small>
            <strong>
              {tokenLabel(snapshot?.current_served_token || snapshot?.currently_serving)}
            </strong>
          </div>
          <div>
            <small>People ahead</small>
            <strong>{snapshot?.people_ahead ?? 'Not available'}</strong>
          </div>
          <div>
            <small>Estimated wait range</small>
            <strong>{range}</strong>
            <span>
              {snapshot?.confidence ? `${snapshot.confidence} confidence` : 'Estimate updating'}
            </span>
          </div>
        </div>
        <div className="queue-guidance">
          <Sparkles />
          <div>
            <strong>Arrival guidance</strong>
            <p>{queueArrivalGuidance(snapshot)}</p>
          </div>
        </div>
      </Card>
      {snapshot?.doctor || snapshot?.location || snapshot?.chamber ? (
        <Card className="instruction-card">
          <MapPin aria-hidden="true" />
          <div>
            <h2>Where to go</h2>
            <p>
              {[
                snapshot?.doctor ? doctorName(snapshot.doctor) : '',
                snapshot?.location?.name,
                snapshot?.chamber?.name,
              ]
                .filter(Boolean)
                .join(' · ')}
            </p>
          </div>
        </Card>
      ) : null}
      <div className="queue-secondary-grid">
        <Card>
          <h2>How this estimate works</h2>
          <p>
            The range uses the doctor’s configured appointment duration and, when enough valid
            visits exist, recent completed service times. It is guidance, not a guaranteed call
            time.
          </p>
          <dl className="mini-definition">
            <div>
              <dt>Confidence</dt>
              <dd>{snapshot?.confidence || 'Not available'}</dd>
            </div>
            <div>
              <dt>Sample band</dt>
              <dd>{snapshot?.sample_count_band || 'Fallback schedule'}</dd>
            </div>
            <div>
              <dt>Calculation</dt>
              <dd>{snapshot?.calculation_version || 'Current pilot version'}</dd>
            </div>
          </dl>
        </Card>
        <Card>
          <h2>Need help onsite?</h2>
          <p>
            Keep this token available and speak with reception if staff give different instructions,
            the status is delayed, or you need to leave the waiting area.
          </p>
          <Link className="text-arrow" to="/contact">
            Hospital contact information <ArrowRight />
          </Link>
        </Card>
      </div>
      <ConfirmDialog
        open={leaveOpen}
        title="Leave this queue?"
        description="Your queue token and appointment will be cancelled. Reception must create a new visit if you return later."
        confirmLabel="Leave queue"
        danger
        loading={leaving}
        confirmDisabled={leaveReason.trim().length < 3}
        onClose={() => {
          setLeaveOpen(false)
          setLeaveReason('')
          setLeaveError(null)
        }}
        onConfirm={leaveQueue}
      >
        {leaveError ? <ErrorNotice error={leaveError} /> : null}
        <Field
          label="Reason"
          id="leave-queue-reason"
          hint="Use a concise operational reason. Do not enter medical details."
          required
        >
          {(props) => (
            <textarea
              {...props}
              value={leaveReason}
              onChange={(event) => setLeaveReason(event.target.value)}
              minLength="3"
              maxLength="500"
              required
            />
          )}
        </Field>
      </ConfirmDialog>
    </div>
  )
}

export function NotificationsPage() {
  const { data, loading, error, reload, setData } = useResource('/notifications/', { list: true })
  const [actionError, setActionError] = useState(null)
  const markRead = async (notification) => {
    try {
      await apiRequest(`/notifications/${notification.id}/read/`, {
        method: 'POST',
        body: {},
        idempotent: false,
      })
      setData((items) =>
        items.map((item) =>
          item.id === notification.id
            ? { ...item, read_at: new Date().toISOString(), is_read: true }
            : item,
        ),
      )
    } catch (requestError) {
      setActionError(requestError)
    }
  }
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="My account"
        title="Notifications"
        description="Privacy-safe updates about your own appointments and queue."
      />
      {actionError ? <ErrorNotice error={actionError} /> : null}
      {loading ? (
        <LoadingState label="Loading notifications" />
      ) : error ? (
        <ErrorNotice error={error} onRetry={reload} />
      ) : data.length ? (
        <div className="notification-list">
          {data.map((notification) => (
            <Card
              className={
                notification.is_read || notification.read_at ? 'notification read' : 'notification'
              }
              key={notification.id}
            >
              <span className="icon-tile">
                <Bell />
              </span>
              <div>
                <div className="notification-head">
                  <h2>{notification.title || 'Hospital update'}</h2>
                  <time dateTime={notification.created_at}>
                    {formatDateTime(notification.created_at)}
                  </time>
                </div>
                <p>
                  {notification.message ||
                    notification.body ||
                    'Open the related visit for more information.'}
                </p>
                {!(notification.is_read || notification.read_at) ? (
                  <Button variant="text" size="sm" onClick={() => markRead(notification)}>
                    Mark as read
                  </Button>
                ) : null}
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <EmptyState
            icon={Inbox}
            title="No notifications"
            description="Appointment and queue updates will appear here."
          />
        </Card>
      )}
    </div>
  )
}

export function PatientProfilePage() {
  const { data, loading, error, reload, setData } = useResource('/me/patient-profile/')
  const [values, setValues] = useState(null)
  const [saveError, setSaveError] = useState(null)
  const [saved, setSaved] = useState(false)
  const [saving, setSaving] = useState(false)
  useEffect(() => {
    if (data) setValues(data)
  }, [data])
  if (loading || !values)
    return loading ? (
      <LoadingState label="Loading your profile" />
    ) : (
      <ErrorNotice error={error} onRetry={reload} />
    )
  const change = (key) => (event) =>
    setValues((current) => ({ ...current, [key]: event.target.value }))
  const save = async (event) => {
    event.preventDefault()
    setSaving(true)
    setSaved(false)
    setSaveError(null)
    try {
      const updated = payload(
        await apiRequest('/me/patient-profile/', {
          method: 'PATCH',
          body: { phone: values.phone, address: values.address },
        }),
      )
      setData(updated)
      setValues(updated)
      setSaved(true)
    } catch (requestError) {
      setSaveError(requestError)
    } finally {
      setSaving(false)
    }
  }
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="My account"
        title="Profile"
        description="Keep your contact details accurate. Identity corrections may require reception review."
      />
      <Card className="form-card">
        <form onSubmit={save}>
          <ErrorSummary
            errors={saveError?.fieldErrors}
            fieldIds={{
              phone: 'profile-phone',
              email: 'profile-email',
              address: 'profile-address',
            }}
          />
          {saveError && !Object.keys(saveError.fieldErrors || {}).length ? (
            <ErrorNotice error={saveError} />
          ) : null}
          {saved ? <SuccessNotice>Your profile changes were saved.</SuccessNotice> : null}
          <div className="identity-panel">
            <span className="avatar avatar-large">
              <UserRound />
            </span>
            <div>
              <small>Medical record number</small>
              <strong>{values.mrn || 'Assigned by the hospital'}</strong>
              <p>{values.full_name}</p>
            </div>
          </div>
          <div className="form-grid">
            <Field
              label="Mobile number"
              id="profile-phone"
              error={saveError?.fieldErrors?.phone}
              required
            >
              {(props) => (
                <input
                  {...props}
                  type="tel"
                  value={values.phone || ''}
                  onChange={change('phone')}
                  required
                />
              )}
            </Field>
            <Field
              label="Email address"
              id="profile-email"
              hint="Contact reception to change a verified email."
            >
              {(props) => <input {...props} type="email" value={values.email || ''} disabled />}
            </Field>
          </div>
          <Field label="Address" id="profile-address">
            {(props) => (
              <textarea
                {...props}
                value={values.address || ''}
                onChange={change('address')}
                maxLength="500"
              />
            )}
          </Field>
          <div className="form-actions">
            <Button type="submit" loading={saving}>
              Save changes
            </Button>
          </div>
        </form>
      </Card>
    </div>
  )
}

export function PatientPrivacyPage() {
  const brand = useBrand()
  const { data, loading, error, reload, setData } = useResource('/me/consents/', { list: true })
  const [saving, setSaving] = useState('')
  const [actionError, setActionError] = useState(null)
  const active = useMemo(() => latestConsentDecisions(data), [data])
  const update = async (purpose, decision) => {
    const noticeVersionId = brand.privacy_notice?.id
    if (!noticeVersionId) {
      setActionError(
        new Error('Privacy choices are unavailable until the hospital publishes its notice.'),
      )
      return
    }
    setSaving(purpose)
    setActionError(null)
    try {
      const created = payload(
        await apiRequest('/me/consents/', {
          method: 'POST',
          body: consentDecisionBody(noticeVersionId, purpose, decision),
        }),
      )
      setData((items) => [created, ...items])
    } catch (requestError) {
      setActionError(requestError)
    } finally {
      setSaving('')
    }
  }
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="My account"
        title="Privacy choices"
        description="Review optional communication choices and the record of your latest decisions."
      />
      {loading ? (
        <LoadingState label="Loading privacy choices" />
      ) : error ? (
        <ErrorNotice error={error} onRetry={reload} />
      ) : (
        <>
          {actionError ? <ErrorNotice error={actionError} /> : null}
          <Card className="privacy-choice">
            <div>
              <span className="icon-tile">
                <Bell />
              </span>
              <div>
                <h2>Email appointment updates</h2>
                <p>
                  Receive minimal messages about booking changes and a secure link to sign in.
                  Messages do not include symptoms or another patient’s information.
                </p>
              </div>
            </div>
            <div className="segmented" aria-label="Email appointment update choice">
              <Button
                variant={active.email_notifications === true ? 'primary' : 'secondary'}
                loading={saving === 'email_notifications'}
                onClick={() => update('email_notifications', true)}
              >
                Allow
              </Button>
              <Button
                variant={active.email_notifications === false ? 'primary' : 'secondary'}
                loading={saving === 'email_notifications'}
                onClick={() => update('email_notifications', false)}
              >
                Do not allow
              </Button>
            </div>
          </Card>
          <Card>
            <div className="card-heading">
              <div>
                <h2>Recent consent record</h2>
                <p>Each decision remains in the append-only hospital history.</p>
              </div>
            </div>
            {data.length ? (
              <Table
                caption="Recent consent decisions"
                columns={['Recorded', 'Purpose', 'Decision', 'Notice', 'Channel']}
              >
                {data.slice(0, 20).map((record) => (
                  <tr key={record.id || `${record.purpose}-${record.created_at}`}>
                    <td>{formatDateTime(record.created_at)}</td>
                    <td>
                      {String(record.purpose || record.consent_type || 'not recorded').replaceAll(
                        '_',
                        ' ',
                      )}
                    </td>
                    <td>
                      <StatusBadge
                        status={(record.decision ?? record.granted) ? 'active' : 'inactive'}
                      >
                        {(record.decision ?? record.granted) ? 'Allowed' : 'Declined'}
                      </StatusBadge>
                    </td>
                    <td>Version {record.notice_version || 'not recorded'}</td>
                    <td>{String(record.channel || 'not recorded').replaceAll('_', ' ')}</td>
                  </tr>
                ))}
              </Table>
            ) : (
              <EmptyState
                title="No consent decisions recorded"
                description="New decisions will appear here after they are recorded."
              />
            )}
          </Card>
          <Card className="article-card">
            <h2>Operational records</h2>
            <p>
              Appointments, queue transitions, onsite payment status, consent changes, and security
              audit events are operational records. They are not optional communication preferences
              and may be retained under the hospital-approved policy.
            </p>
            <Link className="text-arrow" to="/privacy">
              Read the full pilot privacy notice <ArrowRight />
            </Link>
          </Card>
        </>
      )}
    </div>
  )
}
