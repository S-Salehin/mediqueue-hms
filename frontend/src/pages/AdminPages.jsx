import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Bell,
  Building2,
  CalendarDays,
  CheckCircle2,
  FileClock,
  MailWarning,
  MapPin,
  Plus,
  Search,
  Settings,
  ShieldAlert,
  Stethoscope,
  UserPlus,
  UsersRound,
} from 'lucide-react'
import { apiRequest, payload, queryString } from '../api/client'
import { API_ROUTES, adminResourceBody, hospitalSettingsBody, scheduleBody } from '../api/contracts'
import { useBrand } from '../context/BrandContext'
import { useResource } from '../hooks/useResource'
import {
  departmentName,
  doctorName,
  formatDateTime,
  hospitalDateInputValue,
  hospitalDateTimeInputValue,
  hospitalLocalDateTimeToIso,
  safeBrandLogoPath,
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

export function AdminDashboard() {
  const { data, loading, error, reload } = useResource('/dashboards/administrator/')
  if (loading) return <LoadingState label="Loading hospital administration" />
  if (error) return <ErrorNotice error={error} onRetry={reload} />
  const summary = data?.summary || {}
  const alerts = data?.alerts || data?.recent || []
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Hospital administration"
        title="Operational overview"
        description="Configuration status, service activity, and issues that need an authorised owner."
      />
      <div className="metric-grid four">
        <MetricCard
          icon={Stethoscope}
          label="Active doctors"
          value={summary.active_doctors ?? 0}
          detail="Approved profiles"
        />
        <MetricCard
          icon={CalendarDays}
          label="Appointments today"
          value={
            summary.today_appointments ?? summary.appointments_today ?? summary.appointments ?? 0
          }
          detail="All departments"
          tone="green"
        />
        <MetricCard
          icon={UsersRound}
          label="Waiting now"
          value={summary.waiting_now ?? summary.waiting ?? 0}
          detail="Checked in"
          tone="amber"
        />
        <MetricCard
          icon={MailWarning}
          label="Delivery failures"
          value={summary.notification_failures ?? summary.failed_notifications ?? 0}
          detail="Needs review"
          tone="violet"
        />
      </div>
      <div className="dashboard-split">
        <Card>
          <div className="card-heading">
            <div>
              <h2>Operational alerts</h2>
              <p>Safe summaries only. Email bodies and secrets are not shown.</p>
            </div>
          </div>
          {alerts.length ? (
            <div className="alert-list">
              {alerts.map((alert) => (
                <div key={alert.id || `${alert.type}-${alert.created_at}`}>
                  <span className="icon-tile">
                    <ShieldAlert />
                  </span>
                  <div>
                    <strong>{alert.title || alert.event_type || 'Operational notice'}</strong>
                    <p>
                      {alert.detail || alert.summary || 'Review the relevant administration area.'}
                    </p>
                    <small>{formatDateTime(alert.created_at)}</small>
                  </div>
                  <StatusBadge status={alert.status || 'pending'} />
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              icon={CheckCircle2}
              title="No current operational alerts"
              description="New configuration or delivery issues will appear here."
            />
          )}
        </Card>
        <Card>
          <h2>Configuration checklist</h2>
          <div className="config-links">
            <Link to="/admin/departments">
              <Building2 />
              Departments
            </Link>
            <Link to="/admin/locations">
              <MapPin />
              Locations and chambers
            </Link>
            <Link to="/admin/doctors">
              <Stethoscope />
              Doctor profiles
            </Link>
            <Link to="/admin/schedules">
              <CalendarDays />
              Schedules and closures
            </Link>
            <Link to="/admin/settings">
              <Settings />
              Hospital identity
            </Link>
          </div>
        </Card>
      </div>
    </div>
  )
}

const resourceConfigs = {
  departments: {
    eyebrow: 'Hospital structure',
    title: 'Departments',
    description: 'Manage public department names and ordering.',
    icon: Building2,
    endpoint: '/admin/departments/',
    fields: [
      { key: 'name', label: 'Department name', required: true },
      { key: 'description', label: 'Public description', type: 'textarea' },
      { key: 'display_order', label: 'Display order', type: 'number' },
    ],
    columns: ['Department', 'Description', 'Order', 'Status'],
    row: (item) => [
      item.name,
      item.description || 'No public description',
      item.display_order ?? 0,
      <StatusBadge key="status" status={item.is_active === false ? 'inactive' : 'active'} />,
    ],
  },
  locations: {
    eyebrow: 'Hospital structure',
    title: 'Locations',
    description: 'Manage approved hospital sites and patient-facing directions.',
    icon: MapPin,
    endpoint: '/admin/locations/',
    fields: [
      { key: 'name', label: 'Location name', required: true },
      { key: 'code', label: 'Location code', required: true },
      { key: 'address', label: 'Public address', type: 'textarea', required: true },
      { key: 'phone', label: 'Public telephone', type: 'tel' },
      { key: 'email', label: 'Public email', type: 'email' },
    ],
    columns: ['Location', 'Code', 'Address', 'Telephone', 'Status'],
    row: (item) => [
      item.name,
      item.code,
      item.address || 'Not set',
      item.phone || 'Not set',
      <StatusBadge key="status" status={item.is_active === false ? 'inactive' : 'active'} />,
    ],
  },
  doctors: {
    eyebrow: 'Clinical directory',
    title: 'Doctors',
    description: 'Manage approved public doctor profiles and hospital assignments.',
    icon: Stethoscope,
    endpoint: '/admin/doctors/',
    fields: [
      { key: 'user', label: 'Invited doctor account', type: 'staff', required: true },
      { key: 'display_name', label: 'Display name', required: true },
      { key: 'doctor_code', label: 'Doctor code', required: true },
      { key: 'designation', label: 'Designation' },
      {
        key: 'registration_reference',
        label: 'Professional registration reference',
      },
      {
        key: 'consultation_fee_minor',
        label: 'Visit fee in poisha',
        type: 'number',
      },
      { key: 'department_ids', label: 'Departments', type: 'departments', required: true },
      {
        key: 'biography',
        label: 'Approved public biography',
        type: 'textarea',
      },
    ],
    columns: ['Doctor', 'Code', 'Designation', 'Registration', 'Status'],
    row: (item) => [
      doctorName(item),
      item.doctor_code,
      item.designation || 'Not set',
      item.registration_reference || 'Not set',
      <StatusBadge key="status" status={item.is_active === false ? 'inactive' : 'active'} />,
    ],
  },
}

export function AdminResourcePage({ type }) {
  const hospital = useBrand()
  const config = resourceConfigs[type]
  const { data, loading, error, reload, setData } = useResource(config.endpoint, { list: true })
  const { data: staff } = useResource('/admin/staff/', { list: true, enabled: type === 'doctors' })
  const { data: departments } = useResource('/admin/departments/', {
    list: true,
    enabled: type === 'doctors',
  })
  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [values, setValues] = useState({})
  const [saveError, setSaveError] = useState(null)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [deactivate, setDeactivate] = useState(null)
  const [deactivationReason, setDeactivationReason] = useState('')
  const openForm = (item = null) => {
    setEditing(item)
    setValues(
      Object.fromEntries(
        config.fields.map((field) => [
          field.key,
          field.key === 'department_ids'
            ? (item?.departments || []).map((department) => String(department.id || department))
            : (item?.[field.key] ?? ''),
        ]),
      ),
    )
    setFormOpen(true)
    setSaveError(null)
  }
  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setSaveError(null)
    try {
      const path = editing ? `${config.endpoint}${editing.id}/` : config.endpoint
      const saved = payload(
        await apiRequest(path, {
          method: editing ? 'PATCH' : 'POST',
          body: adminResourceBody(type, values, hospital.id, Boolean(editing)),
        }),
      )
      setData((items) =>
        editing ? items.map((item) => (item.id === editing.id ? saved : item)) : [...items, saved],
      )
      setMessage(`${config.title.slice(0, -1)} ${editing ? 'updated' : 'created'}.`)
      setFormOpen(false)
    } catch (requestError) {
      setSaveError(requestError)
    } finally {
      setSaving(false)
    }
  }
  const deactivateItem = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      const saved = payload(
        await apiRequest(`${config.endpoint}${deactivate.id}/deactivate/`, {
          method: 'POST',
          body: { reason: deactivationReason.trim() },
        }),
      )
      setData((items) =>
        items.map((item) =>
          item.id === deactivate.id ? saved || { ...item, is_active: false } : item,
        ),
      )
      setMessage(`${config.title.slice(0, -1)} deactivated.`)
      setDeactivate(null)
      setDeactivationReason('')
    } catch (requestError) {
      setSaveError(requestError)
    } finally {
      setSaving(false)
    }
  }
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow={config.eyebrow}
        title={config.title}
        description={config.description}
        actions={
          <Button onClick={() => openForm()}>
            <Plus />
            Add {config.title.slice(0, -1).toLowerCase()}
          </Button>
        }
      />
      {message ? <SuccessNotice>{message}</SuccessNotice> : null}
      {formOpen ? (
        <Card className="form-card">
          <div className="card-heading">
            <div>
              <h2>
                {editing ? 'Edit' : 'Add'} {config.title.slice(0, -1).toLowerCase()}
              </h2>
              <p>Changes are recorded in the hospital audit trail.</p>
            </div>
            <Button variant="text" onClick={() => setFormOpen(false)}>
              Close
            </Button>
          </div>
          <form onSubmit={submit}>
            <ErrorSummary
              errors={saveError?.fieldErrors}
              fieldIds={Object.fromEntries(
                config.fields.map((field) => [field.key, `${type}-${field.key}`]),
              )}
            />
            {saveError && !Object.keys(saveError.fieldErrors || {}).length ? (
              <ErrorNotice error={saveError} />
            ) : null}
            <div className="form-grid">
              {config.fields.map((field) => (
                <Field
                  label={field.label}
                  id={`${type}-${field.key}`}
                  required={field.required}
                  error={saveError?.fieldErrors?.[field.key]}
                  key={field.key}
                >
                  {(props) =>
                    field.type === 'staff' ? (
                      <select
                        {...props}
                        value={values[field.key] || ''}
                        onChange={(event) =>
                          setValues((current) => ({ ...current, [field.key]: event.target.value }))
                        }
                        required
                      >
                        <option value="">Select an invited doctor account</option>
                        {staff
                          .filter(
                            (person) =>
                              person.is_active !== false &&
                              (person.roles || []).includes('doctor') &&
                              (!person.doctor_profile_id ||
                                String(person.id) === String(values.user)),
                          )
                          .map((person) => (
                            <option key={person.id} value={person.id}>
                              {person.display_name || person.email} ({person.email})
                            </option>
                          ))}
                      </select>
                    ) : field.type === 'departments' ? (
                      <select
                        {...props}
                        multiple
                        value={values[field.key] || []}
                        onChange={(event) =>
                          setValues((current) => ({
                            ...current,
                            [field.key]: Array.from(
                              event.target.selectedOptions,
                              (option) => option.value,
                            ),
                          }))
                        }
                        required
                      >
                        {departments
                          .filter((department) => department.is_active !== false)
                          .map((department) => (
                            <option key={department.id} value={department.id}>
                              {department.name}
                            </option>
                          ))}
                      </select>
                    ) : field.type === 'textarea' ? (
                      <textarea
                        {...props}
                        value={values[field.key] ?? ''}
                        onChange={(event) =>
                          setValues((current) => ({
                            ...current,
                            [field.key]: event.target.value,
                          }))
                        }
                        required={field.required}
                      />
                    ) : (
                      <input
                        {...props}
                        type={field.type || 'text'}
                        value={values[field.key] ?? ''}
                        onChange={(event) =>
                          setValues((current) => ({
                            ...current,
                            [field.key]:
                              field.type === 'number'
                                ? Number(event.target.value)
                                : event.target.value,
                          }))
                        }
                        required={field.required}
                      />
                    )
                  }
                </Field>
              ))}
            </div>
            <div className="form-actions">
              <Button variant="secondary" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" loading={saving}>
                Save {config.title.slice(0, -1).toLowerCase()}
              </Button>
            </div>
          </form>
        </Card>
      ) : null}
      {loading ? (
        <LoadingState label={`Loading ${config.title.toLowerCase()}`} />
      ) : error ? (
        <ErrorNotice error={error} onRetry={reload} />
      ) : data.length ? (
        <Card>
          <Table caption={config.title} columns={[...config.columns, 'Actions']}>
            {data.map((item) => (
              <tr key={item.id}>
                {config.row(item).map((value, index) => (
                  <td data-label={config.columns[index]} key={config.columns[index]}>
                    {typeof value === 'string' ? (
                      index === 0 ? (
                        <strong>{value}</strong>
                      ) : (
                        value
                      )
                    ) : (
                      value
                    )}
                  </td>
                ))}
                <td>
                  <div className="table-actions">
                    <Button variant="text" size="sm" onClick={() => openForm(item)}>
                      Edit
                    </Button>
                    {item.is_active !== false ? (
                      <Button
                        variant="text-danger"
                        size="sm"
                        onClick={() => {
                          setDeactivate(item)
                          setDeactivationReason('')
                          setSaveError(null)
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
        </Card>
      ) : (
        <Card>
          <EmptyState
            icon={config.icon}
            title={`No ${config.title.toLowerCase()} configured`}
            description="Add the first approved record to continue hospital setup."
          />
        </Card>
      )}
      {type === 'locations' ? <ChambersPanel locations={data} /> : null}
      <ConfirmDialog
        open={Boolean(deactivate)}
        title={`Deactivate ${deactivate?.name || deactivate?.display_name || 'this record'}?`}
        description="The record stops appearing in new operational choices. Existing history is preserved."
        confirmLabel="Deactivate"
        danger
        loading={saving}
        confirmDisabled={deactivationReason.trim().length < 3}
        onClose={() => {
          setDeactivate(null)
          setDeactivationReason('')
          setSaveError(null)
        }}
        onConfirm={deactivateItem}
      >
        {saveError ? <ErrorNotice error={saveError} /> : null}
        <Field label="Reason" id={`${type}-deactivation-reason`} required>
          {(props) => (
            <textarea
              {...props}
              value={deactivationReason}
              onChange={(event) => setDeactivationReason(event.target.value)}
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

function ChambersPanel({ locations }) {
  const { data, loading, error, reload, setData } = useResource('/admin/chambers/', { list: true })
  const [form, setForm] = useState({ location: '', name: '' })
  const [editing, setEditing] = useState(null)
  const [deactivate, setDeactivate] = useState(null)
  const [reason, setReason] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [message, setMessage] = useState('')
  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setSaveError(null)
    try {
      const saved = payload(
        await apiRequest(editing ? `/admin/chambers/${editing.id}/` : '/admin/chambers/', {
          method: editing ? 'PATCH' : 'POST',
          body: form,
        }),
      )
      setData((items) =>
        editing ? items.map((item) => (item.id === editing.id ? saved : item)) : [...items, saved],
      )
      setForm({ location: '', name: '' })
      setEditing(null)
      setMessage(`Chamber ${editing ? 'updated' : 'created'}.`)
    } catch (requestError) {
      setSaveError(requestError)
    } finally {
      setSaving(false)
    }
  }
  const deactivateItem = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      const saved = payload(
        await apiRequest(`/admin/chambers/${deactivate.id}/deactivate/`, {
          method: 'POST',
          body: { reason: reason.trim() },
        }),
      )
      setData((items) => items.map((item) => (item.id === deactivate.id ? saved : item)))
      setDeactivate(null)
      setReason('')
      setMessage('Chamber deactivated.')
    } catch (requestError) {
      setSaveError(requestError)
    } finally {
      setSaving(false)
    }
  }
  const locationName = (item) =>
    locations.find((location) => String(location.id) === String(item.location?.id || item.location))
      ?.name || 'Location unavailable'
  return (
    <Card className="form-card">
      <div className="card-heading">
        <div>
          <h2>Chambers</h2>
          <p>Add and maintain the named rooms used by doctor schedules.</p>
        </div>
      </div>
      {message ? <SuccessNotice>{message}</SuccessNotice> : null}
      <form onSubmit={submit}>
        {saveError && !deactivate ? <ErrorNotice error={saveError} /> : null}
        <div className="form-grid">
          <AdminSelect
            label="Location"
            id="chamber-location"
            value={form.location}
            items={locations.filter(
              (item) => item.is_active !== false || String(item.id) === String(form.location),
            )}
            name={(item) => item.name}
            onChange={(value) => setForm((current) => ({ ...current, location: value }))}
          />
          <Field label="Chamber name" id="chamber-name" required>
            {(props) => (
              <input
                {...props}
                value={form.name}
                onChange={(event) =>
                  setForm((current) => ({ ...current, name: event.target.value }))
                }
                required
              />
            )}
          </Field>
        </div>
        <div className="form-actions">
          {editing ? (
            <Button
              variant="secondary"
              onClick={() => {
                setEditing(null)
                setForm({ location: '', name: '' })
                setSaveError(null)
              }}
            >
              Cancel edit
            </Button>
          ) : (
            <span />
          )}
          <Button type="submit" loading={saving}>
            {editing ? 'Save chamber' : 'Add chamber'}
          </Button>
        </div>
      </form>
      {loading ? (
        <LoadingState label="Loading chambers" />
      ) : error ? (
        <ErrorNotice error={error} onRetry={reload} />
      ) : data.length ? (
        <Table caption="Hospital chambers" columns={['Chamber', 'Location', 'Status', 'Actions']}>
          {data.map((item) => (
            <tr key={item.id}>
              <td>
                <strong>{item.name}</strong>
              </td>
              <td>{locationName(item)}</td>
              <td>
                <StatusBadge status={item.is_active === false ? 'inactive' : 'active'} />
              </td>
              <td>
                <div className="table-actions">
                  <Button
                    variant="text"
                    size="sm"
                    onClick={() => {
                      setEditing(item)
                      setForm({ location: item.location?.id || item.location, name: item.name })
                      setSaveError(null)
                    }}
                  >
                    Edit
                  </Button>
                  {item.is_active !== false ? (
                    <Button
                      variant="text-danger"
                      size="sm"
                      onClick={() => {
                        setDeactivate(item)
                        setReason('')
                        setSaveError(null)
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
          title="No chambers configured"
          description="Add a chamber before publishing doctor schedules."
        />
      )}
      <ConfirmDialog
        open={Boolean(deactivate)}
        title={`Deactivate ${deactivate?.name || 'this chamber'}?`}
        description="It will no longer be available for new schedules. Existing history remains."
        confirmLabel="Deactivate chamber"
        danger
        loading={saving}
        confirmDisabled={reason.trim().length < 3}
        onClose={() => {
          setDeactivate(null)
          setReason('')
          setSaveError(null)
        }}
        onConfirm={deactivateItem}
      >
        {saveError ? <ErrorNotice error={saveError} /> : null}
        <Field label="Reason" id="chamber-deactivate-reason" required>
          {(props) => (
            <textarea
              {...props}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              minLength="3"
              maxLength="500"
              required
            />
          )}
        </Field>
      </ConfirmDialog>
    </Card>
  )
}

export function AdminStaffPage() {
  const { data, loading, error, reload, setData } = useResource('/admin/staff/', {
    list: true,
  })
  const [inviteOpen, setInviteOpen] = useState(false)
  const [form, setForm] = useState({ email: '', role: 'doctor' })
  const [sending, setSending] = useState(false)
  const [sendError, setSendError] = useState(null)
  const [sent, setSent] = useState(false)
  const [deactivate, setDeactivate] = useState(null)
  const [reason, setReason] = useState('')
  const deactivateStaff = async () => {
    setSending(true)
    setSendError(null)
    try {
      await apiRequest(`/admin/staff/${deactivate.id}/deactivate/`, {
        method: 'POST',
        body: { reason },
      })
      setData((items) =>
        items.map((item) => (item.id === deactivate.id ? { ...item, is_active: false } : item)),
      )
      setDeactivate(null)
      setReason('')
    } catch (requestError) {
      setSendError(requestError)
    } finally {
      setSending(false)
    }
  }
  const invite = async (event) => {
    event.preventDefault()
    setSending(true)
    setSendError(null)
    try {
      await apiRequest('/admin/staff-invitations/', {
        method: 'POST',
        body: form,
      })
      setSent(true)
      setInviteOpen(false)
      setForm({ email: '', role: 'doctor' })
    } catch (requestError) {
      setSendError(requestError)
    } finally {
      setSending(false)
    }
  }
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Identity and access"
        title="Staff"
        description="Staff accounts are invitation-only and require MFA before operational access."
        actions={
          <Button onClick={() => setInviteOpen((value) => !value)}>
            <UserPlus />
            Invite staff member
          </Button>
        }
      />
      {sent ? (
        <SuccessNotice>
          The invitation was created. Delivery status is available in the notification workspace.
        </SuccessNotice>
      ) : null}
      {inviteOpen ? (
        <Card className="form-card">
          <h2>Invite staff member</h2>
          <form onSubmit={invite}>
            <ErrorSummary
              errors={sendError?.fieldErrors}
              fieldIds={{ email: 'staff-email', role: 'staff-role' }}
            />
            {sendError && !Object.keys(sendError.fieldErrors || {}).length ? (
              <ErrorNotice error={sendError} />
            ) : null}
            <div className="form-grid">
              <Field label="Hospital email" id="staff-email" required>
                {(props) => (
                  <input
                    {...props}
                    type="email"
                    value={form.email}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        email: event.target.value,
                      }))
                    }
                    required
                  />
                )}
              </Field>
              <Field label="Role" id="staff-role" required>
                {(props) => (
                  <select
                    {...props}
                    value={form.role}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        role: event.target.value,
                      }))
                    }
                  >
                    <option value="doctor">Doctor</option>
                    <option value="receptionist">Receptionist</option>
                    <option value="administrator">Administrator</option>
                  </select>
                )}
              </Field>
            </div>
            <div className="form-actions">
              <Button variant="secondary" onClick={() => setInviteOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" loading={sending}>
                Create invitation
              </Button>
            </div>
          </form>
        </Card>
      ) : null}
      {loading ? (
        <LoadingState label="Loading staff access" />
      ) : error ? (
        <ErrorNotice error={error} onRetry={reload} />
      ) : data.length ? (
        <Card>
          <Table
            caption="Hospital staff"
            columns={['Staff member', 'Role', 'MFA', 'Last active', 'Status', 'Action']}
          >
            {data.map((staff) => (
              <tr key={staff.id}>
                <td>
                  <strong>{staff.display_name || staff.full_name}</strong>
                  <small>{staff.email}</small>
                </td>
                <td>{departmentName(staff.roles || staff.role)}</td>
                <td>
                  <StatusBadge
                    status={(staff.mfa_enrolled ?? staff.mfa_enabled) ? 'active' : 'pending'}
                  >
                    {(staff.mfa_enrolled ?? staff.mfa_enabled) ? 'Configured' : 'Required'}
                  </StatusBadge>
                </td>
                <td>{formatDateTime(staff.last_login)}</td>
                <td>
                  <StatusBadge status={staff.is_active === false ? 'inactive' : 'active'} />
                </td>
                <td>
                  {staff.is_active !== false ? (
                    <Button
                      variant="text-danger"
                      size="sm"
                      onClick={() => {
                        setDeactivate(staff)
                        setReason('')
                        setSendError(null)
                      }}
                    >
                      Deactivate access
                    </Button>
                  ) : null}
                </td>
              </tr>
            ))}
          </Table>
        </Card>
      ) : (
        <Card>
          <EmptyState
            icon={UsersRound}
            title="No staff records returned"
            description="Use the invitation action to create controlled staff access."
          />
        </Card>
      )}
      <ConfirmDialog
        open={Boolean(deactivate)}
        title={`Deactivate ${deactivate?.display_name || deactivate?.email || 'this staff account'}?`}
        description="The account immediately loses operational access. Existing audit history remains."
        confirmLabel="Deactivate access"
        danger
        loading={sending}
        confirmDisabled={reason.trim().length < 3}
        onClose={() => setDeactivate(null)}
        onConfirm={deactivateStaff}
      >
        <ErrorSummary
          errors={sendError?.fieldErrors}
          fieldIds={{ reason: 'staff-deactivate-reason' }}
        />
        {sendError && !Object.keys(sendError.fieldErrors || {}).length ? (
          <ErrorNotice error={sendError} />
        ) : null}
        <Field label="Reason" id="staff-deactivate-reason" required>
          {(props) => (
            <textarea
              {...props}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
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

export function AdminSchedulesPage() {
  const hospital = useBrand()
  const { data, loading, error, reload, setData } = useResource('/admin/schedules/', { list: true })
  const { data: doctors } = useResource('/admin/doctors/', { list: true })
  const { data: locations } = useResource('/admin/locations/', { list: true })
  const { data: chambers } = useResource('/admin/chambers/', { list: true })
  const initial = {
    doctor: '',
    location: '',
    chamber: '',
    weekday: '0',
    start_local: '09:00',
    end_local: '13:00',
    slot_duration_minutes: 20,
    capacity_per_slot: 1,
    effective_from: hospitalDateInputValue(),
    effective_to: '',
  }
  const [form, setForm] = useState(initial)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [deactivate, setDeactivate] = useState(null)
  const [deactivationReason, setDeactivationReason] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [message, setMessage] = useState('')

  const openForm = (item = null) => {
    setEditing(item)
    setForm(
      item
        ? {
            doctor: item.doctor?.id || item.doctor,
            location: item.location?.id || item.location,
            chamber: item.chamber?.id || item.chamber,
            weekday: String(item.weekday),
            start_local: String(item.start_local || item.start_time || '09:00').slice(0, 5),
            end_local: String(item.end_local || item.end_time || '13:00').slice(0, 5),
            slot_duration_minutes: item.slot_duration_minutes || 20,
            capacity_per_slot: item.capacity_per_slot || 1,
            effective_from: item.effective_from,
            effective_to: item.effective_to || '',
          }
        : initial,
    )
    setOpen(true)
    setSaveError(null)
  }

  const submit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setSaveError(null)
    try {
      const saved = payload(
        await apiRequest(editing ? `/admin/schedules/${editing.id}/` : '/admin/schedules/', {
          method: editing ? 'PATCH' : 'POST',
          body: scheduleBody(form, hospital.id, Boolean(editing)),
        }),
      )
      setData((items) =>
        editing ? items.map((item) => (item.id === editing.id ? saved : item)) : [...items, saved],
      )
      setMessage(`Recurring schedule ${editing ? 'updated' : 'created'}.`)
      setOpen(false)
      setEditing(null)
      setForm(initial)
    } catch (requestError) {
      setSaveError(requestError)
    } finally {
      setSaving(false)
    }
  }

  const deactivateSchedule = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      const saved = payload(
        await apiRequest(`/admin/schedules/${deactivate.id}/deactivate/`, {
          method: 'POST',
          body: { reason: deactivationReason.trim() },
        }),
      )
      setData((items) => items.map((item) => (item.id === deactivate.id ? saved : item)))
      setDeactivate(null)
      setDeactivationReason('')
      setMessage('Recurring schedule deactivated.')
    } catch (requestError) {
      setSaveError(requestError)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Availability"
        title="Schedules"
        description="Recurring doctor availability. Use schedule exceptions for closures and approved one-off changes."
        actions={
          <Button onClick={() => openForm()}>
            <Plus />
            Add schedule
          </Button>
        }
      />
      {message ? <SuccessNotice>{message}</SuccessNotice> : null}
      {open ? (
        <Card className="form-card">
          <h2>{editing ? 'Edit' : 'Create'} recurring schedule</h2>
          <form onSubmit={submit}>
            <ErrorSummary
              errors={saveError?.fieldErrors}
              fieldIds={{
                doctor: 'schedule-doctor',
                doctor_id: 'schedule-doctor',
                location: 'schedule-location',
                location_id: 'schedule-location',
                chamber: 'schedule-chamber',
                chamber_id: 'schedule-chamber',
                weekday: 'schedule-weekday',
                start_local: 'schedule-start',
                end_local: 'schedule-end',
                slot_duration_minutes: 'schedule-duration',
                capacity_per_slot: 'schedule-capacity',
                effective_from: 'schedule-effective-from',
                effective_to: 'schedule-effective-to',
              }}
            />
            {saveError && !Object.keys(saveError.fieldErrors || {}).length ? (
              <ErrorNotice error={saveError} />
            ) : null}
            <div className="form-grid">
              <AdminSelect
                label="Doctor"
                id="schedule-doctor"
                value={form.doctor}
                items={doctors.filter(
                  (item) => item.is_active !== false || String(item.id) === String(form.doctor),
                )}
                name={doctorName}
                onChange={(value) => setForm((current) => ({ ...current, doctor: value }))}
              />
              <AdminSelect
                label="Location"
                id="schedule-location"
                value={form.location}
                items={locations.filter(
                  (item) => item.is_active !== false || String(item.id) === String(form.location),
                )}
                name={(item) => item.name}
                onChange={(value) =>
                  setForm((current) => ({ ...current, location: value, chamber: '' }))
                }
              />
              <AdminSelect
                label="Chamber"
                id="schedule-chamber"
                value={form.chamber}
                items={chambers.filter(
                  (item) =>
                    String(item.location?.id || item.location) === String(form.location) &&
                    (item.is_active !== false || String(item.id) === String(form.chamber)),
                )}
                name={(item) => item.name}
                onChange={(value) => setForm((current) => ({ ...current, chamber: value }))}
              />
              <Field label="Day of week" id="schedule-weekday" required>
                {(props) => (
                  <select
                    {...props}
                    value={form.weekday}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        weekday: event.target.value,
                      }))
                    }
                  >
                    {[
                      'Monday',
                      'Tuesday',
                      'Wednesday',
                      'Thursday',
                      'Friday',
                      'Saturday',
                      'Sunday',
                    ].map((day, index) => (
                      <option key={day} value={index}>
                        {day}
                      </option>
                    ))}
                  </select>
                )}
              </Field>
              <Field label="Start time" id="schedule-start" required>
                {(props) => (
                  <input
                    {...props}
                    type="time"
                    value={form.start_local}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        start_local: event.target.value,
                      }))
                    }
                    required
                  />
                )}
              </Field>
              <Field label="End time" id="schedule-end" required>
                {(props) => (
                  <input
                    {...props}
                    type="time"
                    value={form.end_local}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        end_local: event.target.value,
                      }))
                    }
                    required
                  />
                )}
              </Field>
              <Field label="Slot duration in minutes" id="schedule-duration" required>
                {(props) => (
                  <input
                    {...props}
                    type="number"
                    min="5"
                    max="60"
                    value={form.slot_duration_minutes}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        slot_duration_minutes: Number(event.target.value),
                      }))
                    }
                    required
                  />
                )}
              </Field>
              <Field label="Capacity per slot" id="schedule-capacity" required>
                {(props) => (
                  <input
                    {...props}
                    type="number"
                    min="1"
                    max="20"
                    value={form.capacity_per_slot}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        capacity_per_slot: Number(event.target.value),
                      }))
                    }
                    required
                  />
                )}
              </Field>
              <Field label="Effective from" id="schedule-effective-from" required>
                {(props) => (
                  <input
                    {...props}
                    type="date"
                    value={form.effective_from}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, effective_from: event.target.value }))
                    }
                    required
                  />
                )}
              </Field>
              <Field label="Effective until" id="schedule-effective-to">
                {(props) => (
                  <input
                    {...props}
                    type="date"
                    min={form.effective_from}
                    value={form.effective_to}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, effective_to: event.target.value }))
                    }
                  />
                )}
              </Field>
            </div>
            <div className="form-actions">
              <Button
                variant="secondary"
                onClick={() => {
                  setOpen(false)
                  setEditing(null)
                  setForm(initial)
                  setSaveError(null)
                }}
              >
                Cancel
              </Button>
              <Button type="submit" loading={saving}>
                {editing ? 'Save schedule' : 'Create schedule'}
              </Button>
            </div>
          </form>
        </Card>
      ) : null}
      {loading ? (
        <LoadingState label="Loading schedules" />
      ) : error ? (
        <ErrorNotice error={error} onRetry={reload} />
      ) : data.length ? (
        <Card>
          <Table
            caption="Recurring schedules"
            columns={[
              'Doctor',
              'Day',
              'Time',
              'Location',
              'Chamber',
              'Capacity',
              'Status',
              'Actions',
            ]}
          >
            {data.map((item) => (
              <tr key={item.id}>
                <td>
                  <strong>{item.doctor_display_name || doctorName(item.doctor)}</strong>
                </td>
                <td>{item.weekday_display || item.day_name || item.weekday}</td>
                <td>
                  {item.start_local || item.start_time} to {item.end_local || item.end_time}
                </td>
                <td>{item.location_name || 'Location unavailable'}</td>
                <td>{item.chamber_name || 'Chamber unavailable'}</td>
                <td>
                  {item.capacity_per_slot || 1} every{' '}
                  {item.slot_duration_minutes || item.slot_minutes} min
                </td>
                <td>
                  <StatusBadge status={item.is_active === false ? 'inactive' : 'active'} />
                </td>
                <td>
                  <div className="table-actions">
                    <Button variant="text" size="sm" onClick={() => openForm(item)}>
                      Edit
                    </Button>
                    {item.is_active !== false ? (
                      <Button
                        variant="text-danger"
                        size="sm"
                        onClick={() => {
                          setDeactivate(item)
                          setDeactivationReason('')
                          setSaveError(null)
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
        </Card>
      ) : (
        <Card>
          <EmptyState
            icon={CalendarDays}
            title="No schedules configured"
            description="Create an approved recurring schedule before exposing appointment availability."
          />
        </Card>
      )}
      <ConfirmDialog
        open={Boolean(deactivate)}
        title="Deactivate this recurring schedule?"
        description="It will stop generating new availability. Existing appointments and history remain."
        confirmLabel="Deactivate schedule"
        danger
        loading={saving}
        confirmDisabled={deactivationReason.trim().length < 3}
        onClose={() => {
          setDeactivate(null)
          setDeactivationReason('')
          setSaveError(null)
        }}
        onConfirm={deactivateSchedule}
      >
        {saveError ? <ErrorNotice error={saveError} /> : null}
        <Field label="Reason" id="schedule-deactivate-reason" required>
          {(props) => (
            <textarea
              {...props}
              value={deactivationReason}
              onChange={(event) => setDeactivationReason(event.target.value)}
              minLength="3"
              maxLength="500"
              required
            />
          )}
        </Field>
      </ConfirmDialog>
      <ScheduleClosures schedules={data} />
    </div>
  )
}

function ScheduleClosures({ schedules }) {
  const { data, loading, error, reload, setData } = useResource('/admin/schedule-exceptions/', {
    list: true,
  })
  const [form, setForm] = useState({ schedule: '', service_date: '', kind: 'closed', reason: '' })
  const [editing, setEditing] = useState(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const create = async (event) => {
    event.preventDefault()
    setSaving(true)
    setSaveError(null)
    try {
      const saved = payload(
        await apiRequest(
          editing ? `/admin/schedule-exceptions/${editing.id}/` : '/admin/schedule-exceptions/',
          { method: editing ? 'PATCH' : 'POST', body: form },
        ),
      )
      setData((items) =>
        editing ? items.map((item) => (item.id === editing.id ? saved : item)) : [...items, saved],
      )
      setForm({ schedule: '', service_date: '', kind: 'closed', reason: '' })
      setEditing(null)
    } catch (requestError) {
      setSaveError(requestError)
    } finally {
      setSaving(false)
    }
  }
  const scheduleName = (scheduleId) => {
    const schedule = schedules.find(
      (item) => String(item.id) === String(scheduleId?.id || scheduleId),
    )
    return schedule
      ? `${schedule.doctor_display_name || doctorName(schedule.doctor)} · ${schedule.weekday_display || schedule.weekday}, ${schedule.start_local}`
      : 'Schedule unavailable'
  }
  return (
    <Card className="form-card">
      <div className="card-heading">
        <div>
          <h2>{editing ? 'Correct schedule closure' : 'Schedule closures'}</h2>
          <p>Close one published schedule for a specific service date.</p>
        </div>
      </div>
      <form onSubmit={create}>
        <ErrorSummary
          errors={saveError?.fieldErrors}
          fieldIds={{
            schedule: 'closure-schedule',
            schedule_id: 'closure-schedule',
            service_date: 'closure-date',
            reason: 'closure-reason',
          }}
        />
        {saveError && !Object.keys(saveError.fieldErrors || {}).length ? (
          <ErrorNotice error={saveError} />
        ) : null}
        <div className="form-grid">
          <AdminSelect
            label="Schedule"
            id="closure-schedule"
            value={form.schedule}
            items={schedules.filter((item) => item.is_active !== false)}
            name={(item) =>
              `${item.doctor_display_name || doctorName(item.doctor)} · ${item.weekday_display || item.weekday}`
            }
            onChange={(value) => setForm((current) => ({ ...current, schedule: value }))}
          />
          <Field label="Service date" id="closure-date" required>
            {(props) => (
              <input
                {...props}
                type="date"
                min={hospitalDateInputValue()}
                value={form.service_date}
                onChange={(event) =>
                  setForm((current) => ({ ...current, service_date: event.target.value }))
                }
                required
              />
            )}
          </Field>
        </div>
        <Field label="Reason" id="closure-reason" required>
          {(props) => (
            <textarea
              {...props}
              value={form.reason}
              onChange={(event) =>
                setForm((current) => ({ ...current, reason: event.target.value }))
              }
              required
              minLength="3"
              maxLength="500"
            />
          )}
        </Field>
        <div className="form-actions">
          {editing ? (
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setEditing(null)
                setForm({ schedule: '', service_date: '', kind: 'closed', reason: '' })
                setSaveError(null)
              }}
            >
              Cancel correction
            </Button>
          ) : null}
          <Button type="submit" loading={saving} disabled={form.reason.trim().length < 3}>
            {editing ? 'Save correction' : 'Record closure'}
          </Button>
        </div>
      </form>
      {loading ? (
        <LoadingState label="Loading schedule closures" />
      ) : error ? (
        <ErrorNotice error={error} onRetry={reload} />
      ) : data.length ? (
        <Table
          caption="Schedule closures"
          columns={['Service date', 'Schedule', 'Reason', 'Action']}
        >
          {data.map((item) => (
            <tr key={item.id}>
              <td>
                <strong>{item.service_date}</strong>
              </td>
              <td>{scheduleName(item.schedule)}</td>
              <td>{item.reason}</td>
              <td>
                <Button
                  variant="text"
                  size="sm"
                  onClick={() => {
                    setEditing(item)
                    setSaveError(null)
                    setForm({
                      schedule: item.schedule?.id || item.schedule,
                      service_date: item.service_date,
                      kind: item.kind || 'closed',
                      reason: item.reason || '',
                    })
                  }}
                >
                  Correct
                </Button>
              </td>
            </tr>
          ))}
        </Table>
      ) : (
        <EmptyState
          title="No schedule closures"
          description="Approved closures will be listed here."
        />
      )}
    </Card>
  )
}

function AdminSelect({ label, id, value, items, name, onChange }) {
  return (
    <Field label={label} id={id} required>
      {(props) => (
        <select
          {...props}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          required
        >
          <option value="">Select {label.toLowerCase()}</option>
          {items.map((item) => (
            <option key={item.id} value={item.id}>
              {name(item)}
            </option>
          ))}
        </select>
      )}
    </Field>
  )
}

export function AdminNotificationsPage() {
  const [status, setStatus] = useState('')
  const { data, loading, error, reload, setData } = useResource(API_ROUTES.notificationOutbox, {
    list: true,
  })
  const [retryTarget, setRetryTarget] = useState(null)
  const [retryReason, setRetryReason] = useState('')
  const [retrying, setRetrying] = useState(false)
  const [retryError, setRetryError] = useState(null)
  const [retryMessage, setRetryMessage] = useState('')
  const visible = status ? data.filter((job) => job.state === status) : data
  const retryDelivery = async () => {
    setRetrying(true)
    setRetryError(null)
    try {
      const saved = payload(
        await apiRequest(`/admin/notification-outbox/${retryTarget.id}/retry/`, {
          method: 'POST',
          body: { reason: retryReason.trim() },
        }),
      )
      setData((items) =>
        items.map((item) => (item.id === retryTarget.id ? { ...item, ...saved } : item)),
      )
      setRetryTarget(null)
      setRetryReason('')
      setRetryMessage('The failed delivery was returned to the notification queue.')
    } catch (requestError) {
      setRetryError(requestError)
    } finally {
      setRetrying(false)
    }
  }
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Notification operations"
        title="Delivery status"
        description="Review delivery metadata and failures without exposing message bodies unnecessarily."
      />
      {retryMessage ? <SuccessNotice>{retryMessage}</SuccessNotice> : null}
      <Card className="filter-row">
        <Field label="Delivery status" id="notification-status">
          {(props) => (
            <select {...props} value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">All statuses</option>
              <option value="pending">Pending</option>
              <option value="processing">Processing</option>
              <option value="failed">Failed</option>
              <option value="dead">Dead letter</option>
              <option value="sent">Sent</option>
            </select>
          )}
        </Field>
      </Card>
      {loading ? (
        <LoadingState label="Loading delivery records" />
      ) : error ? (
        <ErrorNotice error={error} onRetry={reload} />
      ) : visible.length ? (
        <Card>
          <Table
            caption="Notification delivery jobs"
            columns={['Created', 'Template', 'Attempts', 'Failure category', 'Status', 'Action']}
          >
            {visible.map((job) => (
              <tr key={job.id}>
                <td>{formatDateTime(job.created_at)}</td>
                <td>{job.template_key}</td>
                <td>{job.attempt_count ?? 0}</td>
                <td>{job.last_error_category || 'None'}</td>
                <td>
                  <StatusBadge status={job.state} />
                </td>
                <td>
                  {job.state === 'failed' ? (
                    <Button
                      variant="text"
                      size="sm"
                      onClick={() => {
                        setRetryTarget(job)
                        setRetryReason('')
                        setRetryError(null)
                        setRetryMessage('')
                      }}
                    >
                      Retry safely
                    </Button>
                  ) : job.state === 'dead' ? (
                    <span className="helper-text">
                      Restart the original invitation or account recovery workflow.
                    </span>
                  ) : null}
                </td>
              </tr>
            ))}
          </Table>
        </Card>
      ) : (
        <Card>
          <EmptyState
            icon={Bell}
            title="No delivery jobs in this view"
            description="Choose another status or wait for new hospital events."
          />
        </Card>
      )}
      <ConfirmDialog
        open={Boolean(retryTarget)}
        title="Retry this failed delivery?"
        description="Only the stored privacy-safe template data will be queued. Dead token messages cannot be retried here."
        confirmLabel="Return to queue"
        loading={retrying}
        confirmDisabled={retryReason.trim().length < 3}
        onClose={() => {
          setRetryTarget(null)
          setRetryReason('')
          setRetryError(null)
        }}
        onConfirm={retryDelivery}
      >
        {retryError ? <ErrorNotice error={retryError} /> : null}
        <Field label="Operational reason" id="notification-retry-reason" required>
          {(props) => (
            <textarea
              {...props}
              value={retryReason}
              onChange={(event) => setRetryReason(event.target.value)}
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

export function AdminAuditPage() {
  const [filters, setFilters] = useState({
    actor: '',
    event_type: '',
    request_id: '',
    subject_id: '',
    from: '',
    to: '',
  })
  const [applied, setApplied] = useState(filters)
  const { data, loading, error, reload } = useResource(
    `/admin/audit-events/${queryString(applied)}`,
    { list: true },
  )
  const change = (key) => (event) =>
    setFilters((current) => ({ ...current, [key]: event.target.value }))
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Accountability"
        title="Audit trail"
        description="Search immutable business events by approved identifiers. Audit content is read only."
      />
      <Card className="filter-card">
        <form
          onSubmit={(event) => {
            event.preventDefault()
            setApplied(filters)
          }}
        >
          <div className="form-grid three">
            <Field label="Actor" id="audit-actor">
              {(props) => (
                <input
                  {...props}
                  value={filters.actor}
                  onChange={change('actor')}
                  placeholder="Email or UUID"
                />
              )}
            </Field>
            <Field label="Event type" id="audit-event">
              {(props) => (
                <input
                  {...props}
                  value={filters.event_type}
                  onChange={change('event_type')}
                  placeholder="queue.completed"
                />
              )}
            </Field>
            <Field label="Request ID" id="audit-request">
              {(props) => (
                <input {...props} value={filters.request_id} onChange={change('request_id')} />
              )}
            </Field>
            <Field label="Subject UUID" id="audit-subject">
              {(props) => (
                <input {...props} value={filters.subject_id} onChange={change('subject_id')} />
              )}
            </Field>
            <Field label="From" id="audit-from">
              {(props) => (
                <input
                  {...props}
                  type="datetime-local"
                  value={filters.from}
                  onChange={change('from')}
                />
              )}
            </Field>
            <Field label="To" id="audit-to">
              {(props) => (
                <input
                  {...props}
                  type="datetime-local"
                  value={filters.to}
                  onChange={change('to')}
                />
              )}
            </Field>
          </div>
          <div className="form-actions">
            <Button
              variant="secondary"
              onClick={() => {
                const empty = {
                  actor: '',
                  event_type: '',
                  request_id: '',
                  subject_id: '',
                  from: '',
                  to: '',
                }
                setFilters(empty)
                setApplied(empty)
              }}
            >
              Clear
            </Button>
            <Button type="submit">
              <Search />
              Search audit
            </Button>
          </div>
        </form>
      </Card>
      {loading ? (
        <LoadingState label="Loading audit events" />
      ) : error ? (
        <ErrorNotice error={error} onRetry={reload} />
      ) : data.length ? (
        <Card>
          <Table
            caption="Audit events"
            columns={['Time', 'Event', 'Actor', 'Subject', 'Request ID']}
          >
            {data.map((event) => (
              <tr key={event.id}>
                <td>{formatDateTime(event.created_at)}</td>
                <td>
                  <strong>{event.event_type}</strong>
                  <small>{event.summary || ''}</small>
                </td>
                <td>{event.actor_display || event.actor_id || 'System'}</td>
                <td>
                  {event.subject_type}
                  <small>{event.subject_id}</small>
                </td>
                <td>
                  <code>{event.request_id}</code>
                </td>
              </tr>
            ))}
          </Table>
        </Card>
      ) : (
        <Card>
          <EmptyState
            icon={FileClock}
            title="No audit events match"
            description="Change the bounded filters. Original events cannot be edited here."
          />
        </Card>
      )}
    </div>
  )
}

export function AdminSettingsPage() {
  const brand = useBrand()
  const { data, loading, error, reload } = useResource('/admin/settings/')
  const [values, setValues] = useState(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [saved, setSaved] = useState(false)
  useEffect(() => {
    if (data) setValues(hospitalSettingsBody(data))
  }, [data])
  const current = values || hospitalSettingsBody(brand)
  const change = (key) => (event) =>
    setValues((value) => ({ ...(value || brand), [key]: event.target.value }))
  const save = async (event) => {
    event.preventDefault()
    setSaving(true)
    setSaved(false)
    setSaveError(null)
    if (current.logo_url && !safeBrandLogoPath(current.logo_url)) {
      setSaveError(
        new Error(
          'Logo path must begin with one slash and stay on this service, for example /branding/hospital-logo.svg.',
        ),
      )
      setSaving(false)
      return
    }
    try {
      const updated = payload(
        await apiRequest('/admin/settings/', {
          method: 'PATCH',
          body: hospitalSettingsBody(current),
        }),
      )
      setValues(hospitalSettingsBody(updated))
      brand.update?.(updated)
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
        eyebrow="Approved public configuration"
        title="Hospital settings"
        description="Configure public identity and operational values. Application secrets never belong in this screen."
      />
      {loading ? (
        <LoadingState label="Loading hospital settings" />
      ) : error ? (
        <ErrorNotice error={error} onRetry={reload} />
      ) : (
        <Card className="form-card">
          <form onSubmit={save}>
            {saved ? <SuccessNotice>Hospital settings were saved.</SuccessNotice> : null}
            <ErrorSummary
              errors={saveError?.fieldErrors}
              fieldIds={{
                display_name: 'setting-name',
                short_name: 'setting-short-name',
                tagline: 'setting-tagline',
                logo_url: 'setting-logo',
                phone: 'setting-phone',
                email: 'setting-email',
                address: 'setting-address',
                timezone: 'setting-timezone',
                currency: 'setting-currency',
                default_slot_duration_minutes: 'setting-duration',
                late_arrival_minutes: 'setting-late',
                patient_cancellation_cutoff_minutes: 'setting-cancellation-cutoff',
              }}
            />
            {saveError && !Object.keys(saveError.fieldErrors || {}).length ? (
              <ErrorNotice error={saveError} />
            ) : null}
            <div className="form-grid">
              <Field label="Hospital public name" id="setting-name" required>
                {(props) => (
                  <input
                    {...props}
                    value={current.display_name || current.name || ''}
                    onChange={change('display_name')}
                    required
                  />
                )}
              </Field>
              <Field label="Short name" id="setting-short-name">
                {(props) => (
                  <input
                    {...props}
                    value={current.short_name || ''}
                    onChange={change('short_name')}
                    maxLength="12"
                  />
                )}
              </Field>
              <Field label="Public tagline" id="setting-tagline">
                {(props) => (
                  <input
                    {...props}
                    value={current.tagline || ''}
                    onChange={change('tagline')}
                    maxLength="160"
                  />
                )}
              </Field>
              <Field
                label="Logo path"
                id="setting-logo"
                hint="Use an approved file served by this service, for example /branding/hospital-logo.svg. Leave empty to use the built-in mark."
              >
                {(props) => (
                  <input
                    {...props}
                    type="text"
                    value={current.logo_url || ''}
                    onChange={change('logo_url')}
                    placeholder="/branding/hospital-logo.svg"
                  />
                )}
              </Field>
              <Field label="Public telephone" id="setting-phone">
                {(props) => (
                  <input
                    {...props}
                    type="tel"
                    value={current.phone || ''}
                    onChange={change('phone')}
                  />
                )}
              </Field>
              <Field label="Public email" id="setting-email">
                {(props) => (
                  <input
                    {...props}
                    type="email"
                    value={current.email || ''}
                    onChange={change('email')}
                  />
                )}
              </Field>
            </div>
            <Field label="Public address" id="setting-address">
              {(props) => (
                <textarea {...props} value={current.address || ''} onChange={change('address')} />
              )}
            </Field>
            <div className="form-grid">
              <Field label="Timezone" id="setting-timezone" hint="Fixed for this Bangladesh pilot.">
                {(props) => <input {...props} value="Asia/Dhaka" readOnly />}
              </Field>
              <Field
                label="Currency"
                id="setting-currency"
                hint="Onsite records use Bangladeshi taka only."
              >
                {(props) => <input {...props} value="BDT" readOnly />}
              </Field>
              <Field
                label="Default slot duration"
                id="setting-duration"
                hint="Minutes, clamped by the queue calculation rules."
              >
                {(props) => (
                  <input
                    {...props}
                    type="number"
                    min="5"
                    max="60"
                    value={current.default_slot_duration_minutes || 20}
                    onChange={(event) =>
                      setValues((value) => ({
                        ...(value || brand),
                        default_slot_duration_minutes: Number(event.target.value),
                      }))
                    }
                  />
                )}
              </Field>
              <Field
                label="Late arrival threshold"
                id="setting-late"
                hint="Minutes after the booked time before reception reviews arrival."
              >
                {(props) => (
                  <input
                    {...props}
                    type="number"
                    min="0"
                    max="180"
                    value={current.late_arrival_minutes || 15}
                    onChange={(event) =>
                      setValues((value) => ({
                        ...(value || brand),
                        late_arrival_minutes: Number(event.target.value),
                      }))
                    }
                  />
                )}
              </Field>
              <Field
                label="Patient cancellation cutoff"
                id="setting-cancellation-cutoff"
                hint="Minutes before the visit when patient self-service cancellation closes. Use 0 to allow it until the appointment starts."
              >
                {(props) => (
                  <input
                    {...props}
                    type="number"
                    min="0"
                    max="1440"
                    value={current.patient_cancellation_cutoff_minutes ?? 0}
                    onChange={(event) =>
                      setValues((value) => ({
                        ...(value || brand),
                        patient_cancellation_cutoff_minutes: Number(event.target.value),
                      }))
                    }
                  />
                )}
              </Field>
            </div>
            <div className="notice notice-warning">
              <ShieldAlert />
              <p>
                Changing the development codename is expected before public production launch.
                Hospital approval is still required outside this software.
              </p>
            </div>
            <div className="form-actions">
              <Button type="submit" loading={saving}>
                Save approved settings
              </Button>
            </div>
          </form>
        </Card>
      )}
      <PrivacyNoticesPanel />
    </div>
  )
}

function PrivacyNoticesPanel() {
  const { data, loading, error, reload, setData } = useResource('/admin/privacy-notices/', {
    list: true,
  })
  const emptyForm = {
    version: '',
    title: '',
    content: '',
    effective_at: hospitalDateTimeInputValue(),
  }
  const [form, setForm] = useState(emptyForm)
  const [confirming, setConfirming] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [saved, setSaved] = useState(false)
  const create = async () => {
    setSaving(true)
    setSaved(false)
    setSaveError(null)
    try {
      const created = payload(
        await apiRequest('/admin/privacy-notices/', {
          method: 'POST',
          body: {
            ...form,
            effective_at: hospitalLocalDateTimeToIso(form.effective_at),
            publish_and_activate: true,
          },
        }),
      )
      setData((items) => [created, ...items.map((item) => ({ ...item, is_active: false }))])
      setForm({ ...emptyForm, effective_at: hospitalDateTimeInputValue() })
      setConfirming(false)
      setSaved(true)
    } catch (requestError) {
      setSaveError(requestError)
    } finally {
      setSaving(false)
    }
  }
  return (
    <Card className="form-card">
      <div className="card-heading">
        <div>
          <h2>Privacy notice versions</h2>
          <p>
            Every new version is published immediately and becomes the active registration notice.
            Published versions are append only.
          </p>
        </div>
      </div>
      {saved ? (
        <SuccessNotice>The privacy notice version was published and activated.</SuccessNotice>
      ) : null}
      <form
        onSubmit={(event) => {
          event.preventDefault()
          setSaveError(null)
          setConfirming(true)
        }}
      >
        {!confirming ? (
          <ErrorSummary
            errors={saveError?.fieldErrors}
            fieldIds={{
              version: 'notice-version',
              title: 'notice-title',
              effective_at: 'notice-effective',
              content: 'notice-content',
            }}
          />
        ) : null}
        {saveError && !confirming && !Object.keys(saveError.fieldErrors || {}).length ? (
          <ErrorNotice error={saveError} />
        ) : null}
        <div className="form-grid">
          <Field label="Version" id="notice-version" required>
            {(props) => (
              <input
                {...props}
                value={form.version}
                onChange={(event) =>
                  setForm((current) => ({ ...current, version: event.target.value }))
                }
                required
              />
            )}
          </Field>
          <Field label="Title" id="notice-title" required>
            {(props) => (
              <input
                {...props}
                value={form.title}
                onChange={(event) =>
                  setForm((current) => ({ ...current, title: event.target.value }))
                }
                required
              />
            )}
          </Field>
          <Field
            label="Effective date and time"
            id="notice-effective"
            hint="Bangladesh time. Future activation is not allowed."
            required
          >
            {(props) => (
              <input
                {...props}
                type="datetime-local"
                max={hospitalDateTimeInputValue()}
                value={form.effective_at}
                onChange={(event) =>
                  setForm((current) => ({ ...current, effective_at: event.target.value }))
                }
                required
              />
            )}
          </Field>
        </div>
        <Field label="Approved notice text" id="notice-content" required>
          {(props) => (
            <textarea
              {...props}
              rows="12"
              value={form.content}
              onChange={(event) =>
                setForm((current) => ({ ...current, content: event.target.value }))
              }
              required
            />
          )}
        </Field>
        <div className="notice notice-warning">
          <ShieldAlert aria-hidden="true" />
          <p>
            Submitting creates an immutable public notice and replaces the active registration
            notice. Review the exact wording with the hospital owner first.
          </p>
        </div>
        <div className="form-actions">
          <Button type="submit" loading={saving}>
            Review publication
          </Button>
        </div>
      </form>
      {loading ? (
        <LoadingState label="Loading privacy notices" />
      ) : error ? (
        <ErrorNotice error={error} onRetry={reload} />
      ) : data.length ? (
        <Table
          caption="Privacy notice versions"
          columns={['Version', 'Title', 'Effective', 'State']}
        >
          {data.map((notice) => (
            <tr key={notice.id}>
              <td>
                <strong>{notice.version}</strong>
              </td>
              <td>{notice.title}</td>
              <td>{formatDateTime(notice.effective_at)}</td>
              <td>
                <StatusBadge
                  status={notice.is_active ? 'active' : notice.is_published ? 'published' : 'draft'}
                />
              </td>
            </tr>
          ))}
        </Table>
      ) : (
        <EmptyState
          title="No privacy notice published"
          description="Patient registration remains unavailable until an approved notice is published and activated."
        />
      )}
      <ConfirmDialog
        open={confirming}
        title="Publish and activate this privacy notice?"
        description="This action cannot edit or remove earlier versions. New registrations will immediately use this exact text."
        confirmLabel="Publish notice"
        loading={saving}
        onClose={() => {
          setConfirming(false)
          setSaveError(null)
        }}
        onConfirm={create}
      >
        <ErrorSummary
          errors={saveError?.fieldErrors}
          fieldIds={{
            version: 'notice-version',
            title: 'notice-title',
            effective_at: 'notice-effective',
            content: 'notice-content',
          }}
        />
        {saveError && !Object.keys(saveError.fieldErrors || {}).length ? (
          <ErrorNotice error={saveError} />
        ) : null}
        <dl className="mini-definition">
          <div>
            <dt>Version</dt>
            <dd>{form.version}</dd>
          </div>
          <div>
            <dt>Title</dt>
            <dd>{form.title}</dd>
          </div>
          <div>
            <dt>Effective</dt>
            <dd>{formatDateTime(hospitalLocalDateTimeToIso(form.effective_at))}</dd>
          </div>
        </dl>
      </ConfirmDialog>
    </Card>
  )
}
