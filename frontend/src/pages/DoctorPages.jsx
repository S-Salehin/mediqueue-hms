import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  Activity,
  CalendarDays,
  CheckCircle2,
  Clock3,
  Forward,
  PauseCircle,
  PlayCircle,
  RefreshCw,
  RotateCcw,
  Stethoscope,
  UserCheck,
  UsersRound,
} from 'lucide-react'
import { apiRequest } from '../api/client'
import { activeQueueTicket } from '../api/contracts'
import { useQueuePolling } from '../hooks/useQueuePolling'
import { useResource } from '../hooks/useResource'
import { formatDate, formatTime, tokenLabel } from '../utils/format'
import {
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  ErrorNotice,
  Field,
  LoadingState,
  MetricCard,
  OfflineNotice,
  PageHeader,
  StatusBadge,
  Table,
} from '../components/ui'

export function DoctorDashboard() {
  const { data, loading, error, reload } = useResource('/dashboards/doctor/')
  if (loading) return <LoadingState label="Loading today's clinical workspace" />
  if (error) return <ErrorNotice error={error} onRetry={reload} />
  const summary = data?.summary || {}
  const queues = data?.queues || data?.recent || []
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow={formatDate(new Date())}
        title="Today’s overview"
        description="Assigned outpatient schedules and operational queues. Clinical records are outside this pilot."
      />
      <div className="metric-grid four">
        <MetricCard
          icon={CalendarDays}
          label="Appointments"
          value={
            summary.today_appointments ?? summary.total_appointments ?? summary.appointments ?? 0
          }
          detail="Today"
        />
        <MetricCard
          icon={CheckCircle2}
          label="Completed"
          value={summary.completed ?? 0}
          detail="Today"
          tone="green"
        />
        <MetricCard
          icon={UsersRound}
          label="Waiting"
          value={summary.waiting ?? summary.in_queue ?? 0}
          detail="Checked in"
          tone="amber"
        />
        <MetricCard
          icon={Clock3}
          label="Typical service"
          value={summary.estimated_minutes ? `${summary.estimated_minutes} min` : 'Updating'}
          detail="Operational estimate"
          tone="violet"
        />
      </div>
      <Card>
        <div className="card-heading">
          <div>
            <h2>Assigned queues</h2>
            <p>Open a queue to call and progress checked-in patients.</p>
          </div>
        </div>
        {queues.length ? (
          <div className="queue-list">
            {queues.map((queue) => (
              <Link
                key={queue.id || queue.queue_id}
                to={`/doctor/queue/${queue.id || queue.queue_id}`}
              >
                <span className="icon-tile">
                  <Stethoscope />
                </span>
                <span>
                  <strong>
                    {queue.department_name || queue.department?.name || 'Outpatient queue'}
                  </strong>
                  <small>
                    {queue.location_name ||
                      queue.location?.name ||
                      queue.location ||
                      'Assigned location'}{' '}
                    · {queue.waiting_count ?? queue.waiting ?? 0} waiting
                  </small>
                </span>
                <StatusBadge status={queue.state || queue.status || 'active'} />
              </Link>
            ))}
          </div>
        ) : (
          <EmptyState
            icon={CalendarDays}
            title="No assigned queue today"
            description="Your active queues will appear when the hospital schedule opens them."
          />
        )}
      </Card>
    </div>
  )
}

export function DoctorSchedulePage() {
  const { data, loading, error, reload } = useResource('/doctor/schedules/', {
    list: true,
  })
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Read-only pilot view"
        title="My schedule"
        description="Administrators manage schedule changes. Contact the hospital administrator if something is incorrect."
      />
      {loading ? (
        <LoadingState label="Loading assigned schedule" />
      ) : error ? (
        <ErrorNotice error={error} onRetry={reload} />
      ) : data.length ? (
        <Card>
          <Table
            caption="Doctor schedule"
            columns={['Day', 'Time', 'Department', 'Location', 'Slot length', 'Status']}
          >
            {data.map((schedule) => (
              <tr key={schedule.id}>
                <td data-label="Day">
                  <strong>
                    {schedule.day_name || schedule.weekday_display || schedule.weekday}
                  </strong>
                </td>
                <td data-label="Time">
                  {formatTime(schedule.start_local || schedule.start_time)} to{' '}
                  {formatTime(schedule.end_local || schedule.end_time)}
                </td>
                <td data-label="Department">
                  {schedule.department?.name || schedule.department_name}
                </td>
                <td data-label="Location">{schedule.location?.name || schedule.location_name}</td>
                <td data-label="Slot length">
                  {schedule.slot_duration_minutes || schedule.slot_minutes} min
                </td>
                <td data-label="Status">
                  <StatusBadge status={schedule.is_active === false ? 'inactive' : 'active'} />
                </td>
              </tr>
            ))}
          </Table>
        </Card>
      ) : (
        <Card>
          <EmptyState
            icon={CalendarDays}
            title="No schedule assigned"
            description="An administrator must publish an active schedule before appointments can be booked."
          />
        </Card>
      )}
    </div>
  )
}

export function DoctorQueueConsole({ workspaceTitle = 'Doctor queue console' }) {
  const { queueId } = useParams()
  const polling = useQueuePolling(queueId)
  const { snapshot, loading, error, stale, online, lastSuccess, refresh, announcement } = polling
  const [dialog, setDialog] = useState(null)
  const [reason, setReason] = useState('')
  const [acting, setActing] = useState(false)
  const [actionError, setActionError] = useState(null)
  const tickets = snapshot?.tickets || snapshot?.waiting_tickets || []
  const waitingTickets = tickets.filter((ticket) => ticket.state === 'waiting')
  const current = activeQueueTicket(snapshot)
  const action = async (kind, ticket = current) => {
    setActing(true)
    setActionError(null)
    try {
      const paths = {
        call_next: `/queues/${queueId}/call-next/`,
        start: `/queue-tickets/${ticket?.id}/start/`,
        complete: `/queue-tickets/${ticket?.id}/complete/`,
        defer: `/queue-tickets/${ticket?.id}/defer/`,
        restore: `/queue-tickets/${ticket?.id}/restore/`,
        no_show: `/queue-tickets/${ticket?.id}/no-show/`,
        cancel: `/queue-tickets/${ticket?.id}/cancel/`,
      }
      await apiRequest(paths[kind], {
        method: 'POST',
        body: reason ? { reason } : {},
      })
      setDialog(null)
      setReason('')
      await refresh()
    } catch (requestError) {
      setActionError(requestError)
    } finally {
      setActing(false)
    }
  }
  if (loading && !snapshot) return <LoadingState label="Connecting to today's queue" />
  if (error && !snapshot) return <ErrorNotice error={error} onRetry={refresh} />
  const dialogNeedsReason = ['defer', 'restore', 'no_show', 'cancel'].includes(dialog?.kind)
  return (
    <div className="page-stack">
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {announcement}
      </div>
      <PageHeader
        eyebrow={workspaceTitle}
        title={snapshot?.department_name || snapshot?.department?.name || 'Today’s queue'}
        description={`${snapshot?.location_name || snapshot?.location?.name || 'Assigned location'} · Operational first in, first out order`}
        actions={
          <Button variant="secondary" onClick={refresh}>
            <RefreshCw />
            Refresh
          </Button>
        }
      />
      {!online || stale ? (
        <OfflineNotice
          offline={!online}
          stale={stale}
          lastUpdated={lastSuccess ? formatTime(lastSuccess) : null}
        />
      ) : null}
      {actionError ? <ErrorNotice error={actionError} /> : null}
      <div className="doctor-console">
        <Card className="now-serving-card">
          <div className="queue-live-row">
            <span className={stale ? 'stale-pill' : 'live-pill'}>
              <span />
              {stale ? 'Delayed' : 'Connected'}
            </span>
          </div>
          {current ? (
            <>
              <p className="eyebrow">Current token</p>
              <strong className="console-token">{tokenLabel(current.token)}</strong>
              <StatusBadge status={current.state} />
              <div className="minimum-identity">
                <span className="avatar">
                  <UserCheck />
                </span>
                <div>
                  <small>Patient</small>
                  <strong>
                    {current.patient?.full_name ||
                      current.patient_name ||
                      'Identity available at service point'}
                  </strong>
                  <span>{current.patient?.mrn || current.mrn || ''}</span>
                  {current.patient?.date_of_birth ? (
                    <span>Date of birth: {current.patient.date_of_birth}</span>
                  ) : null}
                  {current.patient?.sex && current.patient.sex !== 'unspecified' ? (
                    <span>Sex: {current.patient.sex}</span>
                  ) : null}
                </div>
              </div>
              <div className="console-actions">
                {current.state === 'called' ? (
                  <Button loading={acting} onClick={() => action('start')}>
                    <PlayCircle />
                    Start service
                  </Button>
                ) : null}
                {current.state === 'in_service' ? (
                  <Button onClick={() => setDialog({ kind: 'complete', ticket: current })}>
                    <CheckCircle2 />
                    Complete
                  </Button>
                ) : null}
                {['called', 'waiting'].includes(current.state) ? (
                  <Button
                    variant="secondary"
                    onClick={() => setDialog({ kind: 'defer', ticket: current })}
                  >
                    <PauseCircle />
                    Defer
                  </Button>
                ) : null}
                {['called', 'waiting', 'deferred'].includes(current.state) ? (
                  <Button
                    variant="danger-soft"
                    onClick={() => setDialog({ kind: 'cancel', ticket: current })}
                  >
                    Cancel queue ticket
                  </Button>
                ) : null}
                {['called', 'waiting'].includes(current.state) ? (
                  <Button
                    variant="danger-soft"
                    onClick={() => setDialog({ kind: 'no_show', ticket: current })}
                  >
                    Mark no show
                  </Button>
                ) : null}
              </div>
            </>
          ) : (
            <>
              <span className="hero-icon">
                <UsersRound />
              </span>
              <h2>No patient is active</h2>
              <p>Call the earliest eligible checked-in token when you are ready.</p>
              <Button
                onClick={() => action('call_next')}
                loading={acting}
                disabled={!waitingTickets.length}
              >
                <Forward />
                Call next patient
              </Button>
            </>
          )}
        </Card>
        <Card>
          <div className="card-heading">
            <div>
              <h2>Checked-in queue</h2>
              <p>
                {waitingTickets.length} waiting, {tickets.length} total records
              </p>
            </div>
            {current ? (
              <Button
                onClick={() => action('call_next')}
                loading={acting}
                disabled={
                  ['called', 'in_service'].includes(current.state) || !waitingTickets.length
                }
              >
                <Forward />
                Call next
              </Button>
            ) : null}
          </div>
          {tickets.length ? (
            <Table
              caption="Checked-in patient queue"
              columns={['Token', 'Patient', 'Appointment', 'Status', 'Action']}
            >
              {tickets.map((ticket) => (
                <tr key={ticket.id}>
                  <td data-label="Token">
                    <strong>{tokenLabel(ticket.token)}</strong>
                  </td>
                  <td data-label="Patient">
                    <strong>{ticket.patient?.full_name || ticket.patient_name || 'Patient'}</strong>
                    <small>{ticket.patient?.mrn || ticket.mrn}</small>
                  </td>
                  <td data-label="Appointment">
                    {formatTime(ticket.appointment?.start_at || ticket.appointment_time)}
                  </td>
                  <td data-label="Status">
                    <StatusBadge status={ticket.state} />
                  </td>
                  <td>
                    <div className="table-actions">
                      {ticket.state === 'deferred' ? (
                        <Button
                          variant="text"
                          size="sm"
                          onClick={() => setDialog({ kind: 'restore', ticket })}
                        >
                          <RotateCcw />
                          Restore
                        </Button>
                      ) : null}
                      {ticket.state === 'waiting' ? (
                        <Button
                          variant="text"
                          size="sm"
                          onClick={() => setDialog({ kind: 'defer', ticket })}
                        >
                          Defer
                        </Button>
                      ) : null}
                      {['waiting', 'deferred'].includes(ticket.state) ? (
                        <Button
                          variant="text-danger"
                          size="sm"
                          onClick={() => setDialog({ kind: 'no_show', ticket })}
                        >
                          No show
                        </Button>
                      ) : null}
                      {['waiting', 'deferred'].includes(ticket.state) ? (
                        <Button
                          variant="text-danger"
                          size="sm"
                          onClick={() => setDialog({ kind: 'cancel', ticket })}
                        >
                          Cancel
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
              title="No waiting patients"
              description="New check-ins will appear here automatically."
            />
          )}
        </Card>
      </div>
      <ConfirmDialog
        open={Boolean(dialog)}
        title={dialogTitle(dialog?.kind)}
        description={dialogDescription(dialog?.kind)}
        confirmLabel={dialogLabel(dialog?.kind)}
        danger={['no_show', 'cancel'].includes(dialog?.kind)}
        loading={acting}
        confirmDisabled={dialogNeedsReason && reason.trim().length < 3}
        onClose={() => {
          setDialog(null)
          setReason('')
          setActionError(null)
        }}
        onConfirm={() => action(dialog.kind, dialog.ticket)}
      >
        {actionError ? <ErrorNotice error={actionError} /> : null}
        {dialogNeedsReason ? (
          <Field label="Operational reason" id="queue-action-reason" required>
            {(props) => (
              <textarea
                {...props}
                required
                minLength="3"
                maxLength="240"
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

function dialogTitle(kind) {
  return (
    {
      complete: 'Complete this service?',
      defer: 'Defer this patient?',
      restore: 'Restore this patient?',
      no_show: 'Mark this patient as no show?',
      cancel: 'Cancel this queue ticket?',
    }[kind] || 'Confirm queue action'
  )
}
function dialogLabel(kind) {
  return (
    {
      complete: 'Complete service',
      defer: 'Defer patient',
      restore: 'Restore fairly',
      no_show: 'Mark no show',
      cancel: 'Cancel queue ticket',
    }[kind] || 'Confirm'
  )
}
function dialogDescription(kind) {
  return {
    complete: 'This closes the queue ticket and completes the appointment.',
    defer: 'The patient leaves the active order until an authorised restore action.',
    restore: 'The system returns the patient to the documented fair position.',
    no_show: 'This is a terminal action and requires an operational reason.',
    cancel:
      'This removes the ticket from the active queue and cancels the linked appointment. A reason is required.',
  }[kind]
}
