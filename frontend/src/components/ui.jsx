import { Children, cloneElement, isValidElement, useEffect, useId, useRef } from 'react'
import { AlertCircle, CheckCircle2, Inbox, LoaderCircle, WifiOff, X } from 'lucide-react'
import { ApiError } from '../api/client'

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  className = '',
  type = 'button',
  ...props
}) {
  return (
    <button
      type={type}
      className={`button button-${variant} button-${size} ${className}`}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading ? <LoaderCircle className="size-4 animate-spin" aria-hidden="true" /> : null}
      <span>{children}</span>
    </button>
  )
}

export function Card({ children, className = '', as: Element = 'section', ...props }) {
  return (
    <Element className={`card ${className}`} {...props}>
      {children}
    </Element>
  )
}

export function PageHeader({ eyebrow, title, description, actions }) {
  return (
    <div className="page-header">
      <div>
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <h1>{title}</h1>
        {description ? <p>{description}</p> : null}
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </div>
  )
}

export function Field({ label, error, hint, children, required = false, id: suppliedId }) {
  const generatedId = useId()
  const id = suppliedId || generatedId
  const errorId = `${id}-error`
  const hintId = `${id}-hint`
  const child =
    typeof children === 'function'
      ? children({
          id,
          'aria-invalid': Boolean(error),
          'aria-describedby': error ? errorId : hint ? hintId : undefined,
        })
      : children
  return (
    <div className="field">
      <label htmlFor={id}>
        {label}
        {required ? <span aria-hidden="true"> *</span> : null}
      </label>
      {child}
      {hint && !error ? (
        <p id={hintId} className="field-hint">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="field-error">
          <AlertCircle aria-hidden="true" />
          {Array.isArray(error) ? error.join(' ') : error}
        </p>
      ) : null}
    </div>
  )
}

export function ErrorNotice({ error, title, onRetry, className = '' }) {
  const ref = useRef(null)
  useEffect(() => {
    if (error) ref.current?.focus()
  }, [error])
  if (!error) return null
  const safe =
    error instanceof ApiError
      ? error
      : new ApiError({ title: title || 'Something went wrong', detail: error.message })
  return (
    <div ref={ref} className={`notice notice-error ${className}`} role="alert" tabIndex={-1}>
      <AlertCircle aria-hidden="true" />
      <div>
        <strong>{title || safe.title}</strong>
        <p>{safe.detail}</p>
        {safe.requestId ? <p className="request-id">Support reference: {safe.requestId}</p> : null}
        {onRetry ? (
          <Button variant="text" size="sm" onClick={onRetry}>
            Try again
          </Button>
        ) : null}
      </div>
    </div>
  )
}

export function SuccessNotice({ children }) {
  return (
    <div className="notice notice-success" role="status">
      <CheckCircle2 aria-hidden="true" />
      <p>{children}</p>
    </div>
  )
}

export function LoadingState({ label = 'Loading information' }) {
  return (
    <div className="state-panel" role="status">
      <LoaderCircle className="animate-spin" aria-hidden="true" />
      <p>{label}</p>
    </div>
  )
}

export function EmptyState({
  icon: Icon = Inbox,
  title = 'Nothing here yet',
  description,
  action,
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Icon aria-hidden="true" />
      </span>
      <h2>{title}</h2>
      {description ? <p>{description}</p> : null}
      {action}
    </div>
  )
}

export function OfflineNotice({ offline = false, stale = false, lastUpdated }) {
  const heading = offline
    ? 'You are offline'
    : stale
      ? 'Queue update is delayed'
      : 'Queue updates are current'
  return (
    <div className="notice notice-warning" role="status">
      <WifiOff aria-hidden="true" />
      <div>
        <strong>{heading}</strong>
        <p>
          Showing the last safe update{lastUpdated ? ` from ${lastUpdated}` : ''}. Follow onsite
          staff guidance until the connection returns.
        </p>
      </div>
    </div>
  )
}

const statusLabels = {
  paid_on_site: 'Paid onsite',
  in_service: 'In service',
  no_show: 'No show',
  called: 'Called',
  waiting: 'Waiting',
  confirmed: 'Confirmed',
  completed: 'Completed',
  cancelled: 'Cancelled',
  deferred: 'Deferred',
  unpaid: 'Unpaid',
  waived: 'Waived',
  refunded: 'Refunded',
  active: 'Active',
  inactive: 'Inactive',
  failed: 'Failed',
  sent: 'Sent',
  pending: 'Pending',
}

export function StatusBadge({ status, children }) {
  const value = String(status || '').toLowerCase()
  return (
    <span className={`status status-${value.replaceAll('_', '-')}`}>
      {children || statusLabels[value] || status || 'Unknown'}
    </span>
  )
}

export function MetricCard({ icon: Icon, label, value, detail, tone = 'blue' }) {
  return (
    <Card className="metric-card">
      <span className={`metric-icon metric-${tone}`}>
        <Icon aria-hidden="true" />
      </span>
      <div>
        <p>{label}</p>
        <strong>{value ?? '0'}</strong>
        {detail ? <small>{detail}</small> : null}
      </div>
    </Card>
  )
}

export function Table({ caption, columns, children }) {
  const labelledRows = Children.map(children, (row) => {
    if (!isValidElement(row) || row.type !== 'tr') return row
    const cells = Children.map(row.props.children, (cell, index) => {
      if (!isValidElement(cell) || cell.type !== 'td') return cell
      return cloneElement(cell, {
        'data-label': cell.props['data-label'] || columns[index] || 'Value',
      })
    })
    return cloneElement(row, {}, cells)
  })
  return (
    <div className="table-scroll">
      <table>
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column} scope="col">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{labelledRows}</tbody>
      </table>
    </div>
  )
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = 'Confirm',
  danger = false,
  loading = false,
  confirmDisabled = false,
  onConfirm,
  onClose,
  children,
}) {
  const dialogRef = useRef(null)
  const returnFocusRef = useRef(null)
  const titleId = useId()
  const descriptionId = useId()
  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (open && !dialog.open) {
      returnFocusRef.current = document.activeElement
      dialog.showModal()
      dialog.querySelector('[data-dialog-cancel]')?.focus()
    }
    if (!open && dialog.open) {
      dialog.close()
      returnFocusRef.current?.focus?.()
    }
  }, [open])
  useEffect(() => {
    const dialog = dialogRef.current
    if (!open || !dialog) return undefined
    const keepFocusInside = (event) => {
      if (event.key !== 'Tab') return
      const focusable = [
        ...dialog.querySelectorAll(
          'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], [tabindex]:not([tabindex="-1"])',
        ),
      ]
      if (!focusable.length) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    dialog.addEventListener('keydown', keepFocusInside)
    return () => dialog.removeEventListener('keydown', keepFocusInside)
  }, [open])
  return (
    <dialog
      ref={dialogRef}
      className="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      aria-describedby={description ? descriptionId : undefined}
      onCancel={onClose}
      onClose={onClose}
    >
      <div className="dialog-head">
        <h2 id={titleId}>{title}</h2>
        <button className="icon-button" onClick={onClose} aria-label="Close dialog">
          <X aria-hidden="true" />
        </button>
      </div>
      {description ? <p id={descriptionId}>{description}</p> : null}
      {children}
      <div className="dialog-actions">
        <Button data-dialog-cancel variant="secondary" onClick={onClose}>
          Go back
        </Button>
        <Button
          variant={danger ? 'danger' : 'primary'}
          loading={loading}
          disabled={confirmDisabled}
          onClick={onConfirm}
        >
          {confirmLabel}
        </Button>
      </div>
    </dialog>
  )
}

export function ErrorSummary({ errors, fieldIds = {}, title = 'Please check the form' }) {
  const ref = useRef(null)
  const entries = Object.entries(errors || {}).filter(
    ([, value]) => value?.length || typeof value === 'string',
  )
  useEffect(() => {
    if (entries.length) ref.current?.focus()
  }, [entries.length])
  if (!entries.length) return null
  return (
    <div ref={ref} tabIndex={-1} className="notice notice-error" role="alert">
      <AlertCircle aria-hidden="true" />
      <div>
        <strong>{title}</strong>
        <ul>
          {entries.map(([field, messages]) => (
            <li key={field}>
              <a
                href={`#${fieldIds[field] || field}`}
                onClick={(event) => {
                  const target = document.getElementById(fieldIds[field] || field)
                  if (target) {
                    event.preventDefault()
                    target.focus()
                  }
                }}
              >
                {field.replaceAll('_', ' ')}:{' '}
                {Array.isArray(messages) ? messages.join(' ') : messages}
              </a>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
