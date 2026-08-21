import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  ArrowRight,
  BellRing,
  Building2,
  CalendarCheck2,
  CheckCircle2,
  Clock3,
  HeartHandshake,
  LockKeyhole,
  MapPin,
  Phone,
  Search,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  UsersRound,
} from 'lucide-react'
import { queryString } from '../api/client'
import { useBrand } from '../context/BrandContext'
import { useResource } from '../hooks/useResource'
import { hospitalDateInputValue, money } from '../utils/format'
import {
  Button,
  Card,
  EmptyState,
  ErrorNotice,
  Field,
  LoadingState,
  PageHeader,
  StatusBadge,
} from '../components/ui'

function doctorName(doctor) {
  return (
    doctor.display_name ||
    doctor.full_name ||
    doctor.name ||
    [doctor.first_name, doctor.last_name].filter(Boolean).join(' ') ||
    'Doctor'
  )
}

function departmentName(value) {
  if (Array.isArray(value)) return value.map(departmentName).join(', ') || 'General medicine'
  return typeof value === 'string' ? value : value?.name || value?.title || 'General medicine'
}

export function HomePage() {
  const brand = useBrand()
  return (
    <>
      <section className="hero-section">
        <div className="container hero-grid">
          <div className="hero-copy">
            <p className="eyebrow">
              <span className="pulse-dot" /> Hospital appointments, made clearer
            </p>
            <h1>Your visit should begin with clarity, not uncertainty.</h1>
            <p className="hero-lead">
              Find the right doctor, book an available time, and follow your own queue token after
              reception checks you in.
            </p>
            <div className="hero-actions">
              <Link className="button button-primary button-lg" to="/doctors">
                Find a doctor <ArrowRight />
              </Link>
              <Link className="button button-secondary button-lg" to="/sign-in">
                Sign in
              </Link>
            </div>
            <div className="trust-row">
              <span>
                <ShieldCheck /> Privacy-safe queue view
              </span>
              <span>
                <Clock3 /> Timely status updates
              </span>
              <span>
                <HeartHandshake /> Human decisions stay with staff
              </span>
            </div>
          </div>
          <div
            className="hero-visual"
            aria-label="Example of the personal queue information available after check-in"
          >
            <div className="visual-orbit orbit-one" />
            <div className="visual-orbit orbit-two" />
            <Card className="sample-queue-card">
              <div className="sample-head">
                <span className="icon-tile">
                  <BellRing />
                </span>
                <div>
                  <small>Personal queue view</small>
                  <strong>Visit progress</strong>
                </div>
                <span className="live-pill">
                  <span /> Live
                </span>
              </div>
              <div className="sample-token">
                <small>Your token</small>
                <strong>
                  A<span>-</span>017
                </strong>
                <StatusBadge status="waiting" />
              </div>
              <div className="sample-progress" aria-hidden="true">
                <span />
                <span />
                <span />
                <span />
                <span />
              </div>
              <div className="sample-details">
                <div>
                  <small>Currently serving</small>
                  <strong>A-013</strong>
                </div>
                <div>
                  <small>Estimated wait</small>
                  <strong>18 to 28 min</strong>
                </div>
              </div>
              <p className="sample-guidance">
                <CheckCircle2 /> Stay nearby. Your estimated return window begins in about 12
                minutes.
              </p>
            </Card>
            <div className="floating-note">
              <LockKeyhole />
              <span>
                <strong>Private by design</strong>
                <small>No other patient names shown</small>
              </span>
            </div>
          </div>
        </div>
      </section>

      <section className="section steps-section">
        <div className="container">
          <div className="section-heading">
            <p className="eyebrow">A simpler hospital day</p>
            <h2>Know what happens next</h2>
            <p>
              {brand.name} connects booking, arrival, and queue progress without turning operational
              waiting into medical triage.
            </p>
          </div>
          <div className="steps-grid">
            {[
              [
                Search,
                '01',
                'Choose a doctor',
                'Browse active hospital departments and approved doctor profiles.',
              ],
              [
                CalendarCheck2,
                '02',
                'Book an open time',
                'Select an available date and slot, then review the visit details before confirming.',
              ],
              [
                Building2,
                '03',
                'Check in at reception',
                'Reception confirms your arrival and issues the final privacy-safe queue token.',
              ],
              [
                BellRing,
                '04',
                'Follow your own queue',
                'See the current token, wait range, confidence, and arrival guidance on your device.',
              ],
            ].map(([Icon, number, title, text]) => (
              <Card key={number} className="step-card">
                <div>
                  <span>{number}</span>
                  <Icon />
                </div>
                <h3>{title}</h3>
                <p>{text}</p>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section className="section feature-band">
        <div className="container feature-grid">
          <div>
            <p className="eyebrow">Built around real hospital roles</p>
            <h2>One service, focused views for each person</h2>
            <p>
              Patients get only their own visit information. Doctors see the minimum identity needed
              for assigned queues. Reception handles arrivals. Administrators manage hospital setup
              and accountability.
            </p>
            <Link className="text-arrow" to="/about">
              Read how the service works <ArrowRight />
            </Link>
          </div>
          <div className="role-stack">
            {[
              [UsersRound, 'Patients', 'Book, manage, and follow personal visits'],
              [Stethoscope, 'Doctors', 'Work through the assigned queue'],
              [Building2, 'Hospital teams', 'Coordinate reception and configuration'],
            ].map(([Icon, title, text]) => (
              <div key={title}>
                <span className="icon-tile">
                  <Icon />
                </span>
                <span>
                  <strong>{title}</strong>
                  <small>{text}</small>
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section cta-section">
        <div className="container">
          <div className="cta-card">
            <div>
              <p className="eyebrow">Plan your next visit</p>
              <h2>Start with the hospital directory</h2>
              <p>Availability is confirmed by the hospital schedule at the time of booking.</p>
            </div>
            <Link className="button button-light button-lg" to="/doctors">
              Browse doctors <ArrowRight />
            </Link>
          </div>
        </div>
      </section>
    </>
  )
}

export function DoctorsPage() {
  const [filters, setFilters] = useState({ search: '', department: '' })
  const [applied, setApplied] = useState({ search: '', department: '' })
  const doctorPath = `/public/doctors/${queryString({ search: applied.search, department: applied.department })}`
  const { data: doctors, loading, error, reload } = useResource(doctorPath, { list: true })
  const { data: departments } = useResource('/public/departments/', {
    list: true,
  })
  const submit = (event) => {
    event.preventDefault()
    setApplied(filters)
  }
  return (
    <div className="page-surface">
      <div className="container public-page">
        <PageHeader
          eyebrow="Hospital directory"
          title="Find a doctor"
          description="Search approved profiles by name or department. Bookable times come directly from the active hospital schedule."
        />
        <Card className="filter-card">
          <form onSubmit={submit} className="doctor-filter" role="search">
            <Field label="Doctor name" id="doctor-search">
              {(props) => (
                <div className="input-with-icon">
                  <Search />
                  <input
                    {...props}
                    value={filters.search}
                    onChange={(event) =>
                      setFilters((value) => ({
                        ...value,
                        search: event.target.value,
                      }))
                    }
                    placeholder="Search by name"
                  />
                </div>
              )}
            </Field>
            <Field label="Department" id="doctor-department">
              {(props) => (
                <select
                  {...props}
                  value={filters.department}
                  onChange={(event) =>
                    setFilters((value) => ({
                      ...value,
                      department: event.target.value,
                    }))
                  }
                >
                  <option value="">All departments</option>
                  {departments.map((department) => (
                    <option
                      key={department.id || department.slug}
                      value={department.id || department.slug}
                    >
                      {department.name}
                    </option>
                  ))}
                </select>
              )}
            </Field>
            <Button type="submit">
              <Search />
              Search directory
            </Button>
          </form>
        </Card>
        {loading ? (
          <LoadingState label="Loading doctor directory" />
        ) : error ? (
          <ErrorNotice error={error} onRetry={reload} />
        ) : doctors.length ? (
          <div className="doctor-grid">
            {doctors.map((doctor) => (
              <DoctorCard doctor={doctor} key={doctor.id} />
            ))}
          </div>
        ) : (
          <EmptyState
            icon={Stethoscope}
            title="No matching doctors"
            description="Try another name or department. Only active approved profiles appear here."
            action={
              <Button
                variant="secondary"
                onClick={() => {
                  setFilters({ search: '', department: '' })
                  setApplied({ search: '', department: '' })
                }}
              >
                Clear filters
              </Button>
            }
          />
        )}
      </div>
    </div>
  )
}

function DoctorCard({ doctor }) {
  const name = doctorName(doctor)
  const initials = name
    .split(' ')
    .filter((value) => !value.toLowerCase().startsWith('dr'))
    .slice(0, 2)
    .map((value) => value[0])
    .join('')
  return (
    <Card className="doctor-card">
      <div className="doctor-avatar" aria-hidden="true">
        {initials || 'DR'}
      </div>
      <div className="doctor-card-body">
        <p className="doctor-department">
          {departmentName(doctor.departments || doctor.department || doctor.specialty)}
        </p>
        <h2>{name}</h2>
        {doctor.designation || doctor.qualifications ? (
          <p>{doctor.designation || doctor.qualifications}</p>
        ) : (
          <p>Approved hospital profile</p>
        )}
        <div className="doctor-meta">
          {doctor.location_name || doctor.location ? (
            <span>
              <MapPin />
              {doctor.location_name || departmentName(doctor.location)}
            </span>
          ) : null}
          {doctor.next_available_date ? (
            <span>
              <CalendarCheck2 />
              Next date: {formatDate(doctor.next_available_date)}
            </span>
          ) : null}
        </div>
      </div>
      <Link className="button button-secondary button-md" to={`/doctors/${doctor.id}`}>
        View profile <ArrowRight />
      </Link>
    </Card>
  )
}

export function DoctorDetailPage() {
  const { doctorId } = useParams()
  const [date, setDate] = useState(hospitalDateInputValue)
  const { data: doctor, loading, error, reload } = useResource(`/public/doctors/${doctorId}/`)
  const {
    data: slots,
    loading: slotsLoading,
    error: slotsError,
  } = useResource(
    `/public/doctors/${doctorId}/availability/${queryString({ date_from: date, date_to: date })}`,
    { list: true },
  )
  if (loading)
    return (
      <div className="page-surface">
        <div className="container public-page">
          <LoadingState label="Loading doctor profile" />
        </div>
      </div>
    )
  if (error)
    return (
      <div className="page-surface">
        <div className="container public-page">
          <ErrorNotice error={error} onRetry={reload} />
        </div>
      </div>
    )
  return (
    <div className="page-surface">
      <div className="container public-page">
        <Link className="back-link" to="/doctors">
          Back to doctor directory
        </Link>
        <div className="detail-layout">
          <Card className="doctor-profile-card">
            <div className="doctor-avatar doctor-avatar-large" aria-hidden="true">
              DR
            </div>
            <p className="eyebrow">
              {departmentName(doctor?.departments || doctor?.department || doctor?.specialty)}
            </p>
            <h1>{doctorName(doctor || {})}</h1>
            {doctor?.designation || doctor?.qualifications ? (
              <p>{doctor.designation || doctor.qualifications}</p>
            ) : null}
            <dl className="profile-list">
              {doctor?.registration_reference || doctor?.registration_number ? (
                <>
                  <dt>Professional registration</dt>
                  <dd>{doctor.registration_reference || doctor.registration_number}</dd>
                </>
              ) : null}
              {doctor?.location_name ? (
                <>
                  <dt>Hospital location</dt>
                  <dd>{doctor.location_name}</dd>
                </>
              ) : null}
              {doctor?.consultation_fee_minor !== undefined ? (
                <>
                  <dt>Visit fee</dt>
                  <dd>{money(doctor.consultation_fee_minor)}</dd>
                </>
              ) : null}
            </dl>
          </Card>
          <Card className="availability-card">
            <p className="eyebrow">Available appointments</p>
            <h2>Choose a date</h2>
            <Field label="Appointment date" id="availability-date">
              {(props) => (
                <input
                  {...props}
                  type="date"
                  min={hospitalDateInputValue()}
                  value={date}
                  onChange={(event) => setDate(event.target.value)}
                />
              )}
            </Field>
            {slotsLoading ? (
              <LoadingState label="Checking availability" />
            ) : slotsError ? (
              <ErrorNotice error={slotsError} />
            ) : slots.length ? (
              <div className="slot-list">
                {slots.map((slot) => (
                  <Link
                    className="slot-button"
                    key={slot.start_at}
                    to={`/patient/appointments/new?doctor=${doctorId}&date=${date}&slot=${encodeURIComponent(slot.start_at)}`}
                  >
                    <Clock3 />{' '}
                    <span>
                      <strong>{formatTime(slot.display_start || slot.start_at)}</strong>
                      <small>
                        {slot.available_capacity !== undefined
                          ? `${slot.available_capacity} place${slot.available_capacity === 1 ? '' : 's'} left`
                          : 'Available'}
                      </small>
                    </span>
                    <ArrowRight />
                  </Link>
                ))}
              </div>
            ) : (
              <EmptyState
                icon={CalendarCheck2}
                title="No times on this date"
                description="Choose another date to check the active schedule."
              />
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}

export function AboutPage() {
  return (
    <div className="page-surface">
      <div className="container prose-page">
        <PageHeader
          eyebrow="About the service"
          title="A clearer link between appointments and arrivals"
          description="This pilot helps one hospital coordinate outpatient visits while keeping clinical decisions outside the queue system."
        />
        <div className="about-grid">
          <Card>
            <span className="icon-tile">
              <CalendarCheck2 />
            </span>
            <h2>Appointments</h2>
            <p>
              Patients and authorised reception staff choose only the slots the hospital has made
              available. Capacity is checked again when a booking is confirmed.
            </p>
          </Card>
          <Card>
            <span className="icon-tile">
              <BellRing />
            </span>
            <h2>Operational queue</h2>
            <p>
              The final token is issued at reception. Queue order follows check-in and approved
              operational actions. It is not a severity score and does not replace medical triage.
            </p>
          </Card>
          <Card>
            <span className="icon-tile">
              <ShieldCheck />
            </span>
            <h2>Minimum necessary access</h2>
            <p>
              Each role receives a focused view. Patient-facing status contains tokens and timing
              guidance, never another patient’s identity.
            </p>
          </Card>
        </div>
        <Card className="plain-language">
          <div>
            <p className="eyebrow">Important boundary</p>
            <h2>This is not an electronic medical record</h2>
          </div>
          <p>
            The pilot does not collect symptoms, diagnoses, prescriptions, laboratory results,
            clinical notes, or treatment decisions. If you need urgent medical help, contact the
            hospital or local emergency services directly.
          </p>
        </Card>
      </div>
    </div>
  )
}

export function ContactPage() {
  const brand = useBrand()
  const contactAvailable = brand.phone || brand.email || brand.address
  return (
    <div className="page-surface">
      <div className="container prose-page">
        <PageHeader
          eyebrow="Contact"
          title="Reach the hospital team"
          description="Use the approved hospital contact route for appointment help. Do not send symptoms or private medical information by ordinary email."
        />
        <div className="contact-layout">
          <Card>
            <h2>Hospital contact</h2>
            {contactAvailable ? (
              <div className="contact-list">
                {brand.phone ? (
                  <a href={`tel:${brand.phone}`}>
                    <span className="icon-tile">
                      <Phone />
                    </span>
                    <span>
                      <small>Telephone</small>
                      <strong>{brand.phone}</strong>
                    </span>
                  </a>
                ) : null}
                {brand.email ? (
                  <a href={`mailto:${brand.email}`}>
                    <span className="icon-tile">
                      <BellRing />
                    </span>
                    <span>
                      <small>Email</small>
                      <strong>{brand.email}</strong>
                    </span>
                  </a>
                ) : null}
                {brand.address ? (
                  <div>
                    <span className="icon-tile">
                      <MapPin />
                    </span>
                    <span>
                      <small>Address</small>
                      <strong>{brand.address}</strong>
                    </span>
                  </div>
                ) : null}
              </div>
            ) : (
              <p className="muted-panel">
                Contact details will appear here after the hospital approves them. For now, speak
                with reception onsite.
              </p>
            )}
          </Card>
          <Card className="help-card">
            <span className="hero-icon">
              <HeartHandshake />
            </span>
            <h2>For urgent care</h2>
            <p>
              This website does not assess medical urgency. Contact the hospital directly or use the
              appropriate local emergency service.
            </p>
          </Card>
        </div>
      </div>
    </div>
  )
}

export function PrivacyPage() {
  const brand = useBrand()
  const notice = brand.privacy_notice
  return (
    <div className="page-surface">
      <div className="container prose-page">
        <PageHeader
          eyebrow="Privacy"
          title={notice?.title || 'Privacy notice not yet published'}
          description={
            notice
              ? `Version ${notice.version} · effective ${formatDate(notice.effective_at)}`
              : `Patient registration for ${brand.name} remains unavailable until the hospital publishes its approved notice.`
          }
        />
        {notice ? (
          <Card className="article-card">
            <p className="published-notice">{notice.content}</p>
          </Card>
        ) : null}
        <Card className="article-card">
          <h2>Information used for the pilot</h2>
          <p>
            The service uses account details, patient registration details, appointments, queue
            events, onsite payment status, notification choices, consent decisions, and security
            audit events needed to operate the visit workflow.
          </p>
          <h2>Information intentionally excluded</h2>
          <p>
            The pilot does not collect symptoms, diagnoses, prescriptions, laboratory results,
            clinical notes, or treatment decisions.
          </p>
          <h2>Who can see information</h2>
          <p>
            Patients see only their own records. Doctors see minimum identity for assigned visits.
            Reception staff manage registration, booking, arrival, and onsite payment status.
            Administrators manage configuration and approved audit access.
          </p>
          <h2>Queue privacy</h2>
          <p>
            A patient queue view shows the patient’s token, the currently served token, people
            ahead, a wait range, and arrival guidance. It does not identify any other patient.
          </p>
          <h2>Your choices</h2>
          <p>
            Signed-in patients can review active consent choices from their privacy page.
            Operational and legally required records may need to be retained under the hospital’s
            approved policy.
          </p>
          <h2>Before production use</h2>
          <p>
            The hospital must approve its identity, contact route, privacy wording, retention
            schedule, incident process, and legal basis before this pilot accepts real patient
            information.
          </p>
        </Card>
      </div>
    </div>
  )
}

function formatDate(value) {
  if (!value) return 'Not set'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat('en-BD', {
        dateStyle: 'medium',
        timeZone: 'Asia/Dhaka',
      }).format(date)
}

function formatTime(value) {
  if (!value) return 'Time not set'
  const date = new Date(value)
  if (!Number.isNaN(date.getTime()))
    return new Intl.DateTimeFormat('en-BD', {
      hour: 'numeric',
      minute: '2-digit',
      timeZone: 'Asia/Dhaka',
    }).format(date)
  return value.slice(0, 5)
}
