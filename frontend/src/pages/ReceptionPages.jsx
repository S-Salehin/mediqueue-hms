import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  CalendarCheck2,
  ClipboardCheck,
  CreditCard,
  Plus,
  Search,
  TicketCheck,
  UserPlus,
  UsersRound,
  WalletCards,
} from 'lucide-react'
import { apiRequest, listPayload, payload, queryString } from '../api/client'
import {
  assistedConsentBody,
  patientClaimInvitationBody,
  patientCorrectionBody,
  paymentActionBody,
  receptionAppointmentsPath,
} from '../api/contracts'
import { useResource } from '../hooks/useResource'
import { useBrand } from '../context/BrandContext'
import {
  departmentName,
  doctorName,
  formatDateTime,
  formatTime,
  hospitalDateInputValue,
  money,
  tokenLabel,
} from '../utils/format'
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
  PageHeader,
  StatusBadge,
  SuccessNotice,
  Table,
} from '../components/ui'
import { DoctorQueueConsole } from './DoctorPages'

export function ReceptionDashboard() {
  const { data, loading, error, reload } = useResource('/dashboards/receptionist/')
  if (loading) return <LoadingState label="Loading reception operations" />
  if (error) return <ErrorNotice error={error} onRetry={reload} />
  const summary = data?.summary || {}
  const queues = data?.queues || data?.recent || []
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Front desk"
        title="Today at reception"
        description="Registration, arrivals, queue operations, and onsite payment status."
        actions={
          <Link className="button button-primary button-md" to="/reception/appointments">
            <Plus />
            New visit
          </Link>
        }
      />
      <div className="metric-grid four">
        <MetricCard
          icon={CalendarCheck2}
          label="Appointments"
          value={
            summary.today_appointments ?? summary.appointments ?? summary.total_appointments ?? 0
          }
          detail="Today"
        />
        <MetricCard
          icon={ClipboardCheck}
          label="Checked in"
          value={summary.checked_in ?? 0}
          detail="Arrivals"
          tone="green"
        />
        <MetricCard
          icon={UsersRound}
          label="Waiting"
          value={summary.waiting ?? 0}
          detail="Across queues"
          tone="amber"
        />
        <MetricCard
          icon={WalletCards}
          label="Unpaid"
          value={summary.unpaid ?? 0}
          detail="Onsite records"
          tone="violet"
        />
      </div>
      <div className="dashboard-split">
        <Card>
          <div className="card-heading">
            <div>
              <h2>Active queues</h2>
              <p>Open a queue for reception support.</p>
            </div>
          </div>
          {queues.length ? (
            <div className="queue-list">
              {queues.map((queue) => (
                <Link
                  key={queue.id || queue.queue_id}
                  to={`/reception/queues/${queue.id || queue.queue_id}`}
                >
                  <span className="icon-tile">
                    <TicketCheck />
                  </span>
                  <span>
                    <strong>
                      {queue.department_name || queue.department?.name || 'Hospital queue'}
                    </strong>
                    <small>
                      {queue.location_name || queue.location?.name || 'Location'} ·{' '}
                      {queue.waiting_count ?? queue.waiting ?? 0} waiting
                    </small>
                  </span>
                  <StatusBadge status={queue.state || 'active'} />
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState
              icon={TicketCheck}
              title="No active queues"
              description="Queues appear after schedules open and patients check in."
            />
          )}
        </Card>
        <Card>
          <h2>Quick actions</h2>
          <div className="quick-actions">
            <Link to="/reception/patients">
              <UserPlus />
              Find or register a patient <span>Search before creating a new record</span>
            </Link>
            <Link to="/reception/appointments">
              <ClipboardCheck />
              Check in an appointment <span>Issue the final queue token</span>
            </Link>
            <Link to="/reception/payments">
              <CreditCard />
              Record onsite payment <span>No card details are collected</span>
            </Link>
          </div>
        </Card>
      </div>
    </div>
  )
}

export function ReceptionPatientsPage() {
  const brand = useBrand()
  const [query, setQuery] = useState('')
  const [applied, setApplied] = useState('')
  const [showForm, setShowForm] = useState(false)
  const { data, loading, error, reload } = useResource(
    `/reception/patients/${queryString({ q: applied })}`,
    { list: true, enabled: applied.length >= 2 },
  )
  const [form, setForm] = useState({
    full_name: '',
    date_of_birth: '',
    phone: '',
    email: '',
    sex: '',
    address: '',
    privacy_accepted: false,
  })
  const [duplicates, setDuplicates] = useState([])
  const [checking, setChecking] = useState(false)
  const [creating, setCreating] = useState(false)
  const [formError, setFormError] = useState(null)
  const [created, setCreated] = useState(null)
  const [claimPatient, setClaimPatient] = useState(null)
  const [claimEmail, setClaimEmail] = useState('')
  const [claiming, setClaiming] = useState(false)
  const [claimError, setClaimError] = useState(null)
  const [claimSent, setClaimSent] = useState(false)
  const [correctPatient, setCorrectPatient] = useState(null)
  const [correction, setCorrection] = useState(null)
  const [deactivatePatient, setDeactivatePatient] = useState(null)
  const [consentPatient, setConsentPatient] = useState(null)
  const [consentDecision, setConsentDecision] = useState('')
  const [consentRecorded, setConsentRecorded] = useState(false)
  const [patientReason, setPatientReason] = useState('')
  const [patientActionError, setPatientActionError] = useState(null)
  const [patientActing, setPatientActing] = useState(false)
  const inviteClaim = async () => {
    setClaiming(true)
    setClaimError(null)
    try {
      await apiRequest(`/reception/patients/${claimPatient.id}/claim-invitations/`, {
        method: 'POST',
        body: patientClaimInvitationBody(claimEmail),
      })
      setClaimSent(true)
      setClaimPatient(null)
      setClaimEmail('')
    } catch (requestError) {
      setClaimError(requestError)
    } finally {
      setClaiming(false)
    }
  }
  const change = (key) => (event) =>
    setForm((current) => ({ ...current, [key]: event.target.value }))

  const createPatient = async () => {
    setCreating(true)
    setFormError(null)
    try {
      const patient = payload(
        await apiRequest('/reception/patients/', {
          method: 'POST',
          body: { ...form, privacy_notice_id: brand.privacy_notice?.id },
        }),
      )
      setCreated(patient)
      setDuplicates([])
      setShowForm(false)
      setForm({
        full_name: '',
        date_of_birth: '',
        phone: '',
        email: '',
        sex: '',
        address: '',
        privacy_accepted: false,
      })
      const searchValue = form.phone || form.email || patient.mrn
      setApplied(searchValue)
      setQuery(searchValue)
    } catch (requestError) {
      setFormError(requestError)
    } finally {
      setCreating(false)
    }
  }

  const checkDuplicates = async (event) => {
    event.preventDefault()
    setChecking(true)
    setFormError(null)
    try {
      const result = await apiRequest('/reception/patients/duplicate-check/', {
        method: 'POST',
        body: {
          full_name: form.full_name,
          email: form.email || undefined,
          phone: form.phone,
          date_of_birth: form.date_of_birth,
        },
      })
      const matches = listPayload(result)
      setDuplicates(matches)
      if (!matches.length) await createPatient()
    } catch (requestError) {
      setFormError(requestError)
    } finally {
      setChecking(false)
    }
  }

  const openCorrection = (patient) => {
    setCorrectPatient(patient)
    setCorrection({
      full_name: patient.full_name || '',
      date_of_birth: patient.date_of_birth || '',
      phone: patient.phone || '',
      email: patient.email || '',
      sex: patient.sex || 'unspecified',
      address: patient.address || '',
      reason: '',
    })
    setPatientActionError(null)
  }

  const saveCorrection = async () => {
    setPatientActing(true)
    setPatientActionError(null)
    try {
      const saved = payload(
        await apiRequest(`/reception/patients/${correctPatient.id}/`, {
          method: 'PATCH',
          body: patientCorrectionBody(correction),
        }),
      )
      setCorrectPatient(null)
      setCorrection(null)
      setCreated(saved)
      reload()
    } catch (requestError) {
      setPatientActionError(requestError)
    } finally {
      setPatientActing(false)
    }
  }

  const recordAssistedConsent = async () => {
    setPatientActing(true)
    setPatientActionError(null)
    try {
      await apiRequest(`/reception/patients/${consentPatient.id}/consents/`, {
        method: 'POST',
        body: assistedConsentBody(
          brand.privacy_notice?.id,
          'email_notifications',
          consentDecision === 'allow',
        ),
      })
      setConsentPatient(null)
      setConsentDecision('')
      setConsentRecorded(true)
    } catch (requestError) {
      setPatientActionError(requestError)
    } finally {
      setPatientActing(false)
    }
  }

  const deactivateRecord = async () => {
    setPatientActing(true)
    setPatientActionError(null)
    try {
      await apiRequest(`/reception/patients/${deactivatePatient.id}/deactivate/`, {
        method: 'POST',
        body: { reason: patientReason },
      })
      setDeactivatePatient(null)
      setPatientReason('')
      reload()
    } catch (requestError) {
      setPatientActionError(requestError)
    } finally {
      setPatientActing(false)
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Patient records"
        title="Find or register a patient"
        description="Search before creating a record. Possible duplicates always require human review."
        actions={
          <Button onClick={() => setShowForm((value) => !value)}>
            <UserPlus />
            {showForm ? 'Close registration' : 'Register patient'}
          </Button>
        }
      />
      {created ? (
        <SuccessNotice>
          Patient record {created.mrn || 'was created'}. The account remains unclaimed until the
          approved claiming process is completed.
        </SuccessNotice>
      ) : null}
      {claimSent ? (
        <SuccessNotice>
          The account claim invitation was sent to the verified address.
        </SuccessNotice>
      ) : null}
      {consentRecorded ? (
        <SuccessNotice>
          The patient&apos;s email notification decision was recorded against the current privacy
          notice.
        </SuccessNotice>
      ) : null}
      {showForm ? (
        <Card className="form-card">
          <div className="card-heading">
            <div>
              <h2>Assisted registration</h2>
              <p>Do not invent an email address. Email is optional for an unclaimed profile.</p>
            </div>
          </div>
          <form onSubmit={checkDuplicates}>
            <ErrorSummary
              errors={formError?.fieldErrors}
              fieldIds={{
                full_name: 'patient-full-name',
                date_of_birth: 'patient-dob',
                sex: 'patient-sex',
                phone: 'patient-phone',
                email: 'patient-email',
                address: 'patient-address',
                privacy_accepted: 'patient-privacy',
              }}
            />
            {formError && !Object.keys(formError.fieldErrors || {}).length ? (
              <ErrorNotice error={formError} />
            ) : null}
            <div className="form-grid">
              <Field label="Full name" id="patient-full-name" required>
                {(props) => (
                  <input
                    {...props}
                    value={form.full_name}
                    onChange={change('full_name')}
                    required
                  />
                )}
              </Field>
              <Field label="Date of birth" id="patient-dob" required>
                {(props) => (
                  <input
                    {...props}
                    type="date"
                    max={hospitalDateInputValue()}
                    value={form.date_of_birth}
                    onChange={change('date_of_birth')}
                    required
                  />
                )}
              </Field>
              <Field label="Sex" id="patient-sex" required>
                {(props) => (
                  <select {...props} value={form.sex} onChange={change('sex')} required>
                    <option value="">Select</option>
                    <option value="female">Female</option>
                    <option value="male">Male</option>
                    <option value="other">Other</option>
                    <option value="unspecified">Prefer not to state</option>
                  </select>
                )}
              </Field>
              <Field label="Mobile number" id="patient-phone" required>
                {(props) => (
                  <input
                    {...props}
                    type="tel"
                    pattern="\+[1-9][0-9]{7,14}"
                    value={form.phone}
                    onChange={change('phone')}
                    required
                  />
                )}
              </Field>
              <Field
                label="Email address"
                id="patient-email"
                hint="Leave blank if the patient does not use email."
              >
                {(props) => (
                  <input {...props} type="email" value={form.email} onChange={change('email')} />
                )}
              </Field>
            </div>
            <Field label="Address" id="patient-address" required>
              {(props) => (
                <textarea
                  {...props}
                  value={form.address}
                  onChange={change('address')}
                  required
                  maxLength="500"
                />
              )}
            </Field>
            {brand.privacy_notice ? (
              <div className="privacy-acknowledgement">
                <h3>{brand.privacy_notice.title}</h3>
                <p>Version {brand.privacy_notice.version}</p>
                <div className="published-notice" tabIndex="0">
                  {brand.privacy_notice.content}
                </div>
                <label className="check-field">
                  <input
                    id="patient-privacy"
                    type="checkbox"
                    checked={form.privacy_accepted}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, privacy_accepted: event.target.checked }))
                    }
                    required
                  />
                  <span>
                    The patient or authorised representative was shown this notice and explicitly
                    acknowledged it.
                  </span>
                </label>
              </div>
            ) : (
              <ErrorNotice
                error={
                  new Error(
                    'Assisted registration is unavailable until the hospital publishes its privacy notice.',
                  )
                }
              />
            )}
            <div className="form-actions">
              <Button
                type="submit"
                loading={checking || creating}
                disabled={!brand.privacy_notice?.id || !form.privacy_accepted}
              >
                Check and create
              </Button>
            </div>
          </form>
          {duplicates.length ? (
            <div className="duplicate-panel" role="alert">
              <h3>Possible matching records</h3>
              <p>
                Compare identifiers with the patient. Do not create another record until these
                matches are reviewed.
              </p>
              <Table
                caption="Possible duplicate patients"
                columns={['MRN', 'Name', 'Date of birth', 'Phone']}
              >
                {duplicates.map((patient) => (
                  <tr key={patient.id}>
                    <td data-label="MRN">{patient.mrn}</td>
                    <td data-label="Name">{patient.full_name}</td>
                    <td data-label="Date of birth">{patient.date_of_birth}</td>
                    <td data-label="Phone">{patient.masked_phone || patient.phone}</td>
                  </tr>
                ))}
              </Table>
              <div className="form-actions">
                <Button variant="secondary" onClick={() => setDuplicates([])}>
                  Return to form
                </Button>
                <Button variant="danger-soft" loading={creating} onClick={createPatient}>
                  Reviewed, create separate record
                </Button>
              </div>
            </div>
          ) : null}
        </Card>
      ) : null}
      <Card>
        <form
          className="search-bar"
          role="search"
          onSubmit={(event) => {
            event.preventDefault()
            setApplied(query.trim())
          }}
        >
          <Field
            label="Search patient records"
            id="patient-search"
            hint="Use at least two characters from an MRN, name, phone, or email."
          >
            {(props) => (
              <div className="input-with-icon">
                <Search />
                <input
                  {...props}
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="MRN, name, phone, or email"
                />
              </div>
            )}
          </Field>
          <Button type="submit" disabled={query.trim().length < 2}>
            <Search />
            Search
          </Button>
        </form>
        {applied.length < 2 ? (
          <EmptyState
            icon={Search}
            title="Start with a patient search"
            description="Search results are bounded and visible only to authorised reception staff."
          />
        ) : loading ? (
          <LoadingState label="Searching patient records" />
        ) : error ? (
          <ErrorNotice error={error} onRetry={reload} />
        ) : data.length ? (
          <Table
            caption="Patient search results"
            columns={['MRN', 'Patient', 'Date of birth', 'Contact', 'Status', 'Action']}
          >
            {data.map((patient) => (
              <tr key={patient.id}>
                <td data-label="MRN">
                  <strong>{patient.mrn}</strong>
                </td>
                <td data-label="Patient">
                  <strong>{patient.full_name}</strong>
                </td>
                <td data-label="Date of birth">{patient.date_of_birth}</td>
                <td data-label="Contact">
                  {patient.masked_phone || patient.phone}
                  <small>{patient.email}</small>
                </td>
                <td data-label="Status">
                  <StatusBadge
                    status={
                      patient.is_active === false
                        ? 'inactive'
                        : patient.is_claimed
                          ? 'active'
                          : 'pending'
                    }
                  />
                </td>
                <td>
                  <div className="table-actions">
                    <Button variant="text" size="sm" onClick={() => openCorrection(patient)}>
                      Correct
                    </Button>
                    {patient.is_active !== false && brand.privacy_notice?.id ? (
                      <Button
                        variant="text"
                        size="sm"
                        onClick={() => {
                          setConsentPatient(patient)
                          setConsentDecision('')
                          setPatientActionError(null)
                          setConsentRecorded(false)
                        }}
                      >
                        Record consent
                      </Button>
                    ) : null}
                    {patient.is_active !== false && !patient.is_claimed ? (
                      <Button
                        variant="text"
                        size="sm"
                        onClick={() => {
                          setClaimPatient(patient)
                          setClaimEmail(patient.email || '')
                          setClaimError(null)
                        }}
                      >
                        Invite to claim
                      </Button>
                    ) : null}
                    {patient.is_active !== false ? (
                      <Button
                        variant="text-danger"
                        size="sm"
                        onClick={() => {
                          setDeactivatePatient(patient)
                          setPatientReason('')
                          setPatientActionError(null)
                        }}
                      >
                        Deactivate
                      </Button>
                    ) : null}
                  </div>
                </td>
              </tr>
            ))}
          </Table>
        ) : (
          <EmptyState
            icon={UsersRound}
            title="No matching patient"
            description="Check spelling and identifiers before starting a new registration."
          />
        )}
      </Card>
      <ConfirmDialog
        open={Boolean(claimPatient)}
        title="Invite this patient to claim the record?"
        description="Confirm an email address with the patient. The link is single use and no token is shown here."
        confirmLabel="Send invitation"
        loading={claiming}
        confirmDisabled={!claimEmail.trim()}
        onClose={() => setClaimPatient(null)}
        onConfirm={inviteClaim}
      >
        <ErrorSummary errors={claimError?.fieldErrors} fieldIds={{ email: 'claim-email' }} />
        {claimError && !Object.keys(claimError.fieldErrors || {}).length ? (
          <ErrorNotice error={claimError} />
        ) : null}
        <Field label="Verified email address" id="claim-email" required>
          {(props) => (
            <input
              {...props}
              type="email"
              value={claimEmail}
              onChange={(event) => setClaimEmail(event.target.value)}
              required
            />
          )}
        </Field>
      </ConfirmDialog>
      <ConfirmDialog
        open={Boolean(correctPatient)}
        title={`Correct ${correctPatient?.full_name || 'this patient record'}?`}
        description="Confirm the patient identity before changing it. The previous values and reason remain in history."
        confirmLabel="Save correction"
        loading={patientActing}
        confirmDisabled={
          !correction?.full_name?.trim() ||
          !correction?.phone?.trim() ||
          !correction?.date_of_birth ||
          !correction?.sex ||
          !correction?.address?.trim() ||
          correction?.reason?.trim().length < 3
        }
        onClose={() => {
          setCorrectPatient(null)
          setCorrection(null)
        }}
        onConfirm={saveCorrection}
      >
        <ErrorSummary
          errors={patientActionError?.fieldErrors}
          fieldIds={{
            full_name: 'correction-name',
            date_of_birth: 'correction-dob',
            phone: 'correction-phone',
            email: 'correction-email',
            sex: 'correction-sex',
            address: 'correction-address',
            reason: 'correction-reason',
          }}
        />
        {patientActionError && !Object.keys(patientActionError.fieldErrors || {}).length ? (
          <ErrorNotice error={patientActionError} />
        ) : null}
        {correction ? (
          <div className="form-grid">
            <Field label="Full name" id="correction-name" required>
              {(props) => (
                <input
                  {...props}
                  value={correction.full_name}
                  onChange={(event) =>
                    setCorrection((current) => ({ ...current, full_name: event.target.value }))
                  }
                  required
                />
              )}
            </Field>
            <Field label="Date of birth" id="correction-dob" required>
              {(props) => (
                <input
                  {...props}
                  type="date"
                  max={hospitalDateInputValue()}
                  value={correction.date_of_birth}
                  onChange={(event) =>
                    setCorrection((current) => ({ ...current, date_of_birth: event.target.value }))
                  }
                  required
                />
              )}
            </Field>
            <Field label="Mobile number" id="correction-phone" required>
              {(props) => (
                <input
                  {...props}
                  type="tel"
                  pattern="\+[1-9][0-9]{7,14}"
                  value={correction.phone}
                  onChange={(event) =>
                    setCorrection((current) => ({ ...current, phone: event.target.value }))
                  }
                  required
                />
              )}
            </Field>
            <Field label="Email address" id="correction-email">
              {(props) => (
                <input
                  {...props}
                  type="email"
                  value={correction.email}
                  onChange={(event) =>
                    setCorrection((current) => ({ ...current, email: event.target.value }))
                  }
                />
              )}
            </Field>
            <Field label="Sex" id="correction-sex" required>
              {(props) => (
                <select
                  {...props}
                  value={correction.sex}
                  onChange={(event) =>
                    setCorrection((current) => ({ ...current, sex: event.target.value }))
                  }
                  required
                >
                  <option value="female">Female</option>
                  <option value="male">Male</option>
                  <option value="other">Other</option>
                  <option value="unspecified">Prefer not to state</option>
                </select>
              )}
            </Field>
            <Field label="Address" id="correction-address" required>
              {(props) => (
                <textarea
                  {...props}
                  value={correction.address}
                  onChange={(event) =>
                    setCorrection((current) => ({ ...current, address: event.target.value }))
                  }
                  required
                  minLength="3"
                  maxLength="500"
                />
              )}
            </Field>
            <Field label="Correction reason" id="correction-reason" required>
              {(props) => (
                <textarea
                  {...props}
                  value={correction.reason}
                  onChange={(event) =>
                    setCorrection((current) => ({ ...current, reason: event.target.value }))
                  }
                  required
                  minLength="3"
                  maxLength="500"
                />
              )}
            </Field>
          </div>
        ) : null}
      </ConfirmDialog>
      <ConfirmDialog
        open={Boolean(consentPatient)}
        title={`Record ${consentPatient?.full_name || "this patient's"} decision?`}
        description="Confirm the patient identity, show the current privacy notice, and record only the decision the patient gives. A new append-only consent event will be created."
        confirmLabel="Record decision"
        loading={patientActing}
        confirmDisabled={!brand.privacy_notice?.id || !consentDecision}
        onClose={() => {
          setConsentPatient(null)
          setConsentDecision('')
          setPatientActionError(null)
        }}
        onConfirm={recordAssistedConsent}
      >
        <ErrorSummary
          errors={patientActionError?.fieldErrors}
          fieldIds={{ decision: 'assisted-consent-decision' }}
        />
        {patientActionError && !Object.keys(patientActionError.fieldErrors || {}).length ? (
          <ErrorNotice error={patientActionError} />
        ) : null}
        <div className="muted-panel">
          <strong>{brand.privacy_notice?.title}</strong>
          <p>Version {brand.privacy_notice?.version}</p>
          <p>
            Email messages contain minimal appointment or queue information and a secure sign-in
            link.
          </p>
        </div>
        <Field label="Patient decision" id="assisted-consent-decision" required>
          {(props) => (
            <select
              {...props}
              value={consentDecision}
              onChange={(event) => setConsentDecision(event.target.value)}
              required
            >
              <option value="">Select the decision given</option>
              <option value="allow">Allow email notifications</option>
              <option value="decline">Decline email notifications</option>
            </select>
          )}
        </Field>
      </ConfirmDialog>
      <ConfirmDialog
        open={Boolean(deactivatePatient)}
        title={`Deactivate ${deactivatePatient?.full_name || 'this patient record'}?`}
        description="The record will stop appearing in active searches and new visits. Existing operational history remains."
        confirmLabel="Deactivate record"
        danger
        loading={patientActing}
        confirmDisabled={patientReason.trim().length < 3}
        onClose={() => setDeactivatePatient(null)}
        onConfirm={deactivateRecord}
      >
        <ErrorSummary
          errors={patientActionError?.fieldErrors}
          fieldIds={{ reason: 'patient-deactivate-reason' }}
        />
        {patientActionError && !Object.keys(patientActionError.fieldErrors || {}).length ? (
          <ErrorNotice error={patientActionError} />
        ) : null}
        <Field label="Reason" id="patient-deactivate-reason" required>
          {(props) => (
            <textarea
              {...props}
              value={patientReason}
              onChange={(event) => setPatientReason(event.target.value)}
              required
              minLength="3"
              maxLength="500"
            />
          )}
        </Field>
      </ConfirmDialog>
    </div>
  )
}

function WalkInForm({ doctors, departments, onCreated, onError }) {
  const today = hospitalDateInputValue()
  const [form, setForm] = useState({
    patient_id: '',
    doctor_id: '',
    department_id: '',
    date: today,
    start_at: '',
  })
  const [slots, setSlots] = useState([])
  const [loadingSlots, setLoadingSlots] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [checkInNow, setCheckInNow] = useState(true)
  const [patientQuery, setPatientQuery] = useState('')
  const [patientSearch, setPatientSearch] = useState('')
  const {
    data: patients,
    loading: patientsLoading,
    error: patientsError,
    reload: reloadPatients,
  } = useResource(`/reception/patients/${queryString({ q: patientSearch })}`, {
    list: true,
    enabled: patientSearch.length >= 2,
  })
  useEffect(() => {
    if (!form.doctor_id || !form.date) {
      setSlots([])
      return
    }
    let current = true
    setSlots([])
    setLoadingSlots(true)
    apiRequest(
      `/public/doctors/${form.doctor_id}/availability/${queryString({ date_from: form.date, date_to: form.date })}`,
    )
      .then((result) => {
        if (current) setSlots(listPayload(result))
      })
      .catch((requestError) => {
        if (current) onError(requestError)
      })
      .finally(() => {
        if (current) setLoadingSlots(false)
      })
    return () => {
      current = false
    }
  }, [form.doctor_id, form.date, onError])
  const selected = slots.find((slot) => slot.start_at === form.start_at)
  const submit = async (event) => {
    event.preventDefault()
    const currentPatientSelected = patients.some(
      (patient) => String(patient.id) === String(form.patient_id),
    )
    if (!selected || !currentPatientSelected) {
      onError(new Error('Select a patient from the current search results and an available time.'))
      return
    }
    setSubmitting(true)
    onError(null)
    try {
      const created = payload(
        await apiRequest(checkInNow ? '/reception/walk-ins/' : '/appointments/', {
          method: 'POST',
          body: {
            patient_id: form.patient_id,
            schedule_id: selected.schedule_id,
            department_id: form.department_id,
            start_at: selected.start_at,
          },
        }),
      )
      onCreated(created, checkInNow)
    } catch (requestError) {
      onError(requestError)
    } finally {
      setSubmitting(false)
    }
  }
  return (
    <form onSubmit={submit}>
      <div className="form-grid">
        <Field
          label="Find patient"
          id="walk-in-patient-search"
          hint="Search by MRN, name, phone, or email."
          required
        >
          {(props) => (
            <div className="input-with-action">
              <input
                {...props}
                value={patientQuery}
                onChange={(event) => setPatientQuery(event.target.value)}
              />
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setForm((current) => ({ ...current, patient_id: '' }))
                  setPatientSearch(patientQuery.trim())
                }}
                disabled={patientQuery.trim().length < 2}
              >
                Search
              </Button>
            </div>
          )}
        </Field>
        {patientsLoading ? (
          <LoadingState label="Searching patient records" />
        ) : patientsError ? (
          <ErrorNotice error={patientsError} onRetry={reloadPatients} />
        ) : patients.length ? (
          <div className="patient-choice-list" role="radiogroup" aria-label="Matching patients">
            {patients.map((patient) => (
              <label
                className={String(form.patient_id) === String(patient.id) ? 'selected' : ''}
                key={patient.id}
              >
                <input
                  type="radio"
                  name="walk-in-patient"
                  value={patient.id}
                  checked={String(form.patient_id) === String(patient.id)}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, patient_id: event.target.value }))
                  }
                />
                <span>
                  <strong>{patient.full_name}</strong>
                  <small>
                    {patient.mrn}, born {patient.date_of_birth}
                  </small>
                </span>
              </label>
            ))}
          </div>
        ) : patientSearch ? (
          <EmptyState
            title="No matching patient"
            description="Return to patient registration if the record does not exist."
          />
        ) : null}
        <Field label="Department" id="walk-in-department" required>
          {(props) => (
            <select
              {...props}
              value={form.department_id}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  department_id: event.target.value,
                  doctor_id: '',
                  start_at: '',
                }))
              }
              required
            >
              <option value="">Select department</option>
              {departments.map((item) => (
                <option value={item.id} key={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label="Doctor" id="walk-in-doctor" required>
          {(props) => (
            <select
              {...props}
              value={form.doctor_id}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  doctor_id: event.target.value,
                  start_at: '',
                }))
              }
              required
            >
              <option value="">Select doctor</option>
              {doctors
                .filter(
                  (doctor) =>
                    !form.department_id ||
                    doctor.departments?.some((item) => String(item.id) === form.department_id),
                )
                .map((doctor) => (
                  <option value={doctor.id} key={doctor.id}>
                    {doctorName(doctor)}
                  </option>
                ))}
            </select>
          )}
        </Field>
        <Field label="Service date" id="walk-in-date" required>
          {(props) => (
            <input
              {...props}
              type="date"
              min={today}
              value={form.date}
              onChange={(event) => {
                setCheckInNow(event.target.value === today)
                setForm((current) => ({
                  ...current,
                  date: event.target.value,
                  start_at: '',
                }))
              }}
              required
            />
          )}
        </Field>
        <Field
          label="Available time"
          id="walk-in-time"
          hint={loadingSlots ? 'Checking the active schedule.' : ''}
          required
        >
          {(props) => (
            <select
              {...props}
              value={form.start_at}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  start_at: event.target.value,
                }))
              }
              required
              disabled={!form.doctor_id || loadingSlots}
            >
              <option value="">Select an open time</option>
              {slots.map((slot) => (
                <option value={slot.start_at} key={slot.start_at}>
                  {formatTime(slot.display_start || slot.start_at)} {slot.available_capacity}{' '}
                  available
                </option>
              ))}
            </select>
          )}
        </Field>
      </div>
      <label className="check-field">
        <input
          type="checkbox"
          checked={checkInNow}
          disabled={form.date !== today}
          onChange={(event) => setCheckInNow(event.target.checked)}
        />
        <span>
          {form.date === today
            ? 'Check in now and issue a queue token. Clear this for a future assisted booking.'
            : 'Future appointments cannot be checked in today.'}
        </span>
      </label>
      <div className="form-actions">
        <Button
          type="submit"
          loading={submitting}
          disabled={
            !selected ||
            !form.patient_id ||
            !patients.some((patient) => String(patient.id) === String(form.patient_id))
          }
        >
          {checkInNow ? 'Create walk-in and check in' : 'Book appointment for patient'}
        </Button>
      </div>
    </form>
  )
}

export function ReceptionAppointmentsPage() {
  const [date, setDate] = useState(hospitalDateInputValue)
  const [showWalkIn, setShowWalkIn] = useState(false)
  const [reference, setReference] = useState('')
  const [appliedReference, setAppliedReference] = useState('')
  const { data, loading, error, reload, setData } = useResource(
    receptionAppointmentsPath(date, appliedReference),
    { list: true },
  )
  const { data: doctors } = useResource('/public/doctors/', { list: true })
  const { data: departments } = useResource('/public/departments/', {
    list: true,
  })
  const [actionError, setActionError] = useState(null)
  const [result, setResult] = useState(null)
  const [actingId, setActingId] = useState('')
  const [cancelTarget, setCancelTarget] = useState(null)
  const [cancelReason, setCancelReason] = useState('')
  const checkIn = async (appointment) => {
    setActingId(appointment.id)
    setActionError(null)
    try {
      const checked = payload(
        await apiRequest(`/reception/appointments/${appointment.id}/check-in/`, {
          method: 'POST',
          body: {},
        }),
      )
      setResult(
        `Checked in. Queue token ${tokenLabel(checked.token || checked.queue_ticket?.token)}.`,
      )
      setData((items) =>
        items.map((item) =>
          item.id === appointment.id ? { ...item, queue: checked.queue_ticket || checked } : item,
        ),
      )
    } catch (requestError) {
      setActionError(requestError)
    } finally {
      setActingId('')
    }
  }
  const cancelAppointment = async () => {
    setActingId(cancelTarget.id)
    setActionError(null)
    try {
      const cancelled = payload(
        await apiRequest(`/appointments/${cancelTarget.id}/cancel/`, {
          method: 'POST',
          body: { reason: cancelReason.trim() },
        }),
      )
      setData((items) => items.map((item) => (item.id === cancelTarget.id ? cancelled : item)))
      setResult('Appointment cancelled. The change was recorded in history.')
      setCancelTarget(null)
      setCancelReason('')
    } catch (requestError) {
      setActionError(requestError)
    } finally {
      setActingId('')
    }
  }
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Reception appointments"
        title="Bookings and arrivals"
        description="Find today’s booking, confirm patient identity, then check in once."
        actions={
          <Button onClick={() => setShowWalkIn((value) => !value)}>
            <Plus />
            {showWalkIn ? 'Close walk-in form' : 'Add walk-in'}
          </Button>
        }
      />
      {result ? <SuccessNotice>{result}</SuccessNotice> : null}
      {actionError ? <ErrorNotice error={actionError} /> : null}
      {showWalkIn ? (
        <Card className="form-card">
          <h2>Book or check in a patient</h2>
          <p className="helper-text">
            Search and register the patient first. Book a future appointment, or keep check-in
            selected for a patient who is already onsite.
          </p>
          <WalkInForm
            doctors={doctors}
            departments={departments}
            onError={setActionError}
            onCreated={(created, checkedIn) => {
              setResult(
                checkedIn
                  ? `Walk-in created and checked in. Queue token ${tokenLabel(created.token || created.ticket?.token || created.queue_ticket?.token)}.`
                  : 'The appointment was booked for the patient.',
              )
              setShowWalkIn(false)
              reload()
            }}
          />
        </Card>
      ) : null}
      <Card className="filter-card">
        <form
          className="appointment-filters"
          onSubmit={(event) => {
            event.preventDefault()
            setAppliedReference(reference.trim())
          }}
        >
          <Field label="Service date" id="reception-date">
            {(props) => (
              <input
                {...props}
                type="date"
                value={date}
                onChange={(event) => setDate(event.target.value)}
              />
            )}
          </Field>
          <Field
            label="Find appointment"
            id="appointment-reference"
            hint="Search by patient name or MRN."
          >
            {(props) => (
              <div className="input-with-icon">
                <Search />
                <input
                  {...props}
                  value={reference}
                  onChange={(event) => setReference(event.target.value)}
                  placeholder="Patient name or MRN"
                />
              </div>
            )}
          </Field>
          <Button type="submit">
            <Search />
            Search
          </Button>
        </form>
      </Card>
      {loading ? (
        <LoadingState label="Loading appointments" />
      ) : error ? (
        <ErrorNotice error={error} onRetry={reload} />
      ) : data.length ? (
        <Card>
          <Table
            caption="Reception appointment list"
            columns={[
              'Time',
              'Patient',
              'Doctor',
              'Location',
              'Status',
              'Arrival',
              'Payment',
              'Actions',
            ]}
          >
            {data.map((appointment) => (
              <tr key={appointment.id}>
                <td data-label="Time">{formatDateTime(appointment.start_at)}</td>
                <td data-label="Patient">
                  <strong>{appointment.patient?.full_name}</strong>
                  <small>{appointment.patient?.mrn}</small>
                </td>
                <td data-label="Doctor">
                  <strong>{doctorName(appointment.doctor)}</strong>
                  <small>{departmentName(appointment.department)}</small>
                </td>
                <td data-label="Location">{departmentName(appointment.location)}</td>
                <td data-label="Status">
                  <StatusBadge status={appointment.status} />
                </td>
                <td data-label="Arrival">
                  {appointment.queue || appointment.queue_ticket ? (
                    <StatusBadge
                      status={
                        appointment.queue?.state || appointment.queue_ticket?.state || 'waiting'
                      }
                    />
                  ) : appointment.status === 'confirmed' && date === hospitalDateInputValue() ? (
                    <Button
                      size="sm"
                      loading={actingId === appointment.id}
                      onClick={() => checkIn(appointment)}
                    >
                      <ClipboardCheck />
                      Check in
                    </Button>
                  ) : null}
                </td>
                <td>
                  <Link
                    className="table-action"
                    to={`/reception/payments?appointment=${appointment.id}`}
                  >
                    Open payment
                  </Link>
                </td>
                <td>
                  {appointment.status === 'confirmed' &&
                  !appointment.queue &&
                  !appointment.queue_ticket ? (
                    <div className="table-actions">
                      <Link
                        className="table-action"
                        to={`/reception/appointments/${appointment.id}/reschedule`}
                      >
                        Reschedule
                      </Link>
                      <Button
                        variant="text-danger"
                        size="sm"
                        onClick={() => {
                          setCancelTarget(appointment)
                          setCancelReason('')
                          setActionError(null)
                        }}
                      >
                        Cancel
                      </Button>
                    </div>
                  ) : null}
                </td>
              </tr>
            ))}
          </Table>
        </Card>
      ) : (
        <Card>
          <EmptyState
            icon={CalendarCheck2}
            title="No matching appointments"
            description="Change the date or search text. Walk-ins can be created with the action above."
          />
        </Card>
      )}
      <ConfirmDialog
        open={Boolean(cancelTarget)}
        title="Cancel this appointment?"
        description="The slot will be released and the patient will see the updated status. Checked-in visits must be handled from the queue console."
        confirmLabel="Cancel appointment"
        danger
        loading={actingId === cancelTarget?.id}
        confirmDisabled={cancelReason.trim().length < 3}
        onClose={() => {
          setCancelTarget(null)
          setCancelReason('')
          setActionError(null)
        }}
        onConfirm={cancelAppointment}
      >
        {actionError ? <ErrorNotice error={actionError} /> : null}
        <Field label="Reason" id="reception-cancel-reason" required>
          {(props) => (
            <textarea
              {...props}
              value={cancelReason}
              onChange={(event) => setCancelReason(event.target.value)}
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

export function ReceptionQueuePage() {
  return <DoctorQueueConsole workspaceTitle="Reception queue console" />
}

export function ReceptionPaymentsPage() {
  const [searchParams] = useSearchParams()
  const [query, setQuery] = useState('')
  const [appliedQuery, setAppliedQuery] = useState('')
  const [loadedId, setLoadedId] = useState(searchParams.get('appointment') || '')
  const {
    data: matches,
    loading: matchesLoading,
    error: matchesError,
    reload: reloadMatches,
  } = useResource(`/appointments/${queryString({ q: appliedQuery })}`, {
    list: true,
    enabled: appliedQuery.length >= 2,
  })
  const {
    data: payment,
    loading,
    error,
    reload,
  } = useResource(`/appointments/${loadedId}/payment/`, {
    enabled: Boolean(loadedId),
  })
  const [dialog, setDialog] = useState(null)
  const [reason, setReason] = useState('')
  const [reference, setReference] = useState('')
  const [acting, setActing] = useState(false)
  const [actionError, setActionError] = useState(null)
  const [success, setSuccess] = useState('')
  const record = async () => {
    setActing(true)
    setActionError(null)
    try {
      await apiRequest(`/appointments/${loadedId}/payment/actions/`, {
        method: 'POST',
        body: paymentActionBody(dialog, { reason, reference }),
      })
      setSuccess(`Payment status updated to ${dialog.replaceAll('_', ' ')}.`)
      setDialog(null)
      setReason('')
      setReference('')
      reload()
    } catch (requestError) {
      setActionError(requestError)
    } finally {
      setActing(false)
    }
  }
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Onsite records only"
        title="Payments"
        description="Record a hospital collection decision. Never enter card numbers, mobile wallet credentials, PINs, or banking secrets."
      />
      {success ? <SuccessNotice>{success}</SuccessNotice> : null}
      <Card>
        <form
          className="search-bar"
          onSubmit={(event) => {
            event.preventDefault()
            setAppliedQuery(query.trim())
            setLoadedId('')
          }}
        >
          <Field
            label="Find appointment"
            id="payment-appointment"
            hint="Search by patient name or MRN."
          >
            {(props) => (
              <div className="input-with-icon">
                <Search />
                <input
                  {...props}
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  required
                />
              </div>
            )}
          </Field>
          <Button type="submit" disabled={query.trim().length < 2}>
            Search
          </Button>
        </form>
      </Card>
      {appliedQuery ? (
        matchesLoading ? (
          <LoadingState label="Searching appointments" />
        ) : matchesError ? (
          <ErrorNotice error={matchesError} onRetry={reloadMatches} />
        ) : matches.length ? (
          <Card>
            <Table
              caption="Matching appointments"
              columns={['Patient', 'Appointment', 'Doctor', 'Payment', 'Action']}
            >
              {matches.map((appointment) => (
                <tr key={appointment.id}>
                  <td>
                    <strong>{appointment.patient?.full_name}</strong>
                    <small>{appointment.patient?.mrn}</small>
                  </td>
                  <td>{formatDateTime(appointment.start_at)}</td>
                  <td>{doctorName(appointment.doctor)}</td>
                  <td>
                    <StatusBadge status={appointment.payment_state || 'unpaid'} />
                  </td>
                  <td>
                    <Button variant="text" size="sm" onClick={() => setLoadedId(appointment.id)}>
                      Open payment
                    </Button>
                  </td>
                </tr>
              ))}
            </Table>
          </Card>
        ) : (
          <Card>
            <EmptyState
              title="No matching appointment"
              description="Check the patient details or appointment reference."
            />
          </Card>
        )
      ) : null}
      {loadedId ? (
        loading ? (
          <LoadingState label="Loading payment record" />
        ) : error ? (
          <ErrorNotice error={error} onRetry={reload} />
        ) : (
          <Card className="payment-card">
            <div>
              <p className="eyebrow">Appointment payment</p>
              <h2>{payment?.patient?.full_name || 'Authorised appointment'}</h2>
              <p>{payment?.patient?.mrn || 'Onsite payment record'}</p>
            </div>
            <div className="payment-amount">
              <small>Visit amount</small>
              <strong>{money(payment?.amount_minor || 0, payment?.currency)}</strong>
              <StatusBadge status={payment?.state || 'unpaid'} />
            </div>
            <div className="card-actions">
              {(payment?.state || 'unpaid') === 'unpaid' ? (
                <>
                  <Button onClick={() => setDialog('paid_on_site')}>Record paid onsite</Button>
                  <Button variant="secondary" onClick={() => setDialog('waived')}>
                    Record waiver
                  </Button>
                </>
              ) : null}
              {payment?.state === 'paid_on_site' ? (
                <Button variant="danger-soft" onClick={() => setDialog('refunded')}>
                  Record refund
                </Button>
              ) : null}
            </div>
          </Card>
        )
      ) : (
        <Card>
          <EmptyState
            icon={CreditCard}
            title="Open an appointment payment"
            description="Search for a patient or open payment from the appointment workspace."
          />
        </Card>
      )}
      <ConfirmDialog
        open={Boolean(dialog)}
        title={`Record ${dialog?.replaceAll('_', ' ') || 'payment action'}?`}
        description="This creates an audit event. It does not move money or contact a payment provider."
        confirmLabel="Record status"
        loading={acting}
        confirmDisabled={dialog !== 'paid_on_site' && reason.trim().length < 3}
        onClose={() => {
          setDialog(null)
          setActionError(null)
        }}
        onConfirm={record}
      >
        <ErrorSummary
          errors={actionError?.fieldErrors}
          fieldIds={{ reference: 'payment-reference', reason: 'payment-reason' }}
        />
        {actionError && !Object.keys(actionError.fieldErrors || {}).length ? (
          <ErrorNotice error={actionError} />
        ) : null}
        <Field
          label="Receipt or counter reference"
          id="payment-reference"
          hint="Use the hospital receipt reference, not card or wallet credentials."
        >
          {(props) => (
            <input
              {...props}
              value={reference}
              onChange={(event) => setReference(event.target.value)}
            />
          )}
        </Field>
        {dialog !== 'paid_on_site' ? (
          <Field label="Reason" id="payment-reason" required>
            {(props) => (
              <textarea
                {...props}
                required
                minLength="3"
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
            )}
          </Field>
        ) : null}
      </ConfirmDialog>
    </div>
  )
}
