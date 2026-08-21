import { useMemo, useState } from 'react'
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import {
  ArrowRight,
  CheckCircle2,
  Eye,
  EyeOff,
  KeyRound,
  LockKeyhole,
  Mail,
  ShieldCheck,
  UserRound,
} from 'lucide-react'
import { apiRequest, payload } from '../api/client'
import {
  mfaReplacementStartBody,
  patientClaimAcceptBody,
  patientRegistrationBody,
  staffInvitationAcceptBody,
} from '../api/contracts'
import { useAuth } from '../context/AuthContext'
import { useBrand } from '../context/BrandContext'
import { hospitalDateInputValue } from '../utils/format'
import { Brand } from '../components/Brand'
import { SkipLink } from '../components/SkipLink'
import {
  Button,
  Card,
  ErrorNotice,
  ErrorSummary,
  Field,
  PageHeader,
  SuccessNotice,
} from '../components/ui'

function dashboardFor(user) {
  const roles = user?.roles || []
  if (roles.includes('administrator') || roles.includes('admin')) return '/admin'
  if (roles.includes('receptionist')) return '/reception'
  if (roles.includes('doctor')) return '/doctor'
  return '/patient'
}

function AuthFrame({
  eyebrow,
  title,
  description,
  children,
  asideTitle = 'Your visit, one clear step at a time',
}) {
  return (
    <>
      <SkipLink />
      <main id="main-content" className="auth-page">
        <div className="auth-shell">
          <aside className="auth-aside">
            <Brand />
            <div>
              <p className="eyebrow">Hospital access</p>
              <h1>{asideTitle}</h1>
              <p>
                Book approved appointments and follow your own queue without exposing anyone else’s
                identity.
              </p>
            </div>
            <ul>
              <li>
                <CheckCircle2 />
                One secure sign-in for every role
              </li>
              <li>
                <ShieldCheck />
                Session protection and staff verification
              </li>
              <li>
                <LockKeyhole />
                No authentication tokens stored in the browser
              </li>
            </ul>
          </aside>
          <section className="auth-content">
            <div className="auth-mobile-brand">
              <Brand />
            </div>
            <p className="eyebrow">{eyebrow}</p>
            <h2>{title}</h2>
            <p className="auth-description">{description}</p>
            {children}
          </section>
        </div>
      </main>
    </>
  )
}

export function SignInPage() {
  const { user, signIn, verifyMfa } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [values, setValues] = useState({ email: '', password: '' })
  const [showPassword, setShowPassword] = useState(false)
  const [challenge, setChallenge] = useState(null)
  const [code, setCode] = useState('')
  const [useRecoveryCode, setUseRecoveryCode] = useState(false)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  if (user) return <Navigate replace to={dashboardFor(user)} />
  const submit = async (event) => {
    event.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const result = await signIn(values)
      if (result.mfaRequired) setChallenge(result.challenge_id || result.challenge || 'pending')
      else navigate(location.state?.from?.pathname || '/app', { replace: true })
    } catch (requestError) {
      setError(requestError)
    } finally {
      setLoading(false)
    }
  }
  const submitMfa = async (event) => {
    event.preventDefault()
    setLoading(true)
    setError(null)
    try {
      await verifyMfa(challenge, code)
      navigate('/app', { replace: true })
    } catch (requestError) {
      setError(requestError)
    } finally {
      setLoading(false)
    }
  }
  return (
    <AuthFrame
      eyebrow={challenge ? 'Staff verification' : 'Welcome back'}
      title={challenge ? 'Enter your verification code' : 'Sign in to your account'}
      description={
        challenge
          ? 'Open your authenticator app and enter the current six-digit code.'
          : 'The hospital role assigned to your account determines the workspace you can open.'
      }
    >
      <ErrorSummary
        errors={error?.fieldErrors}
        fieldIds={
          challenge
            ? { code: 'mfa-code', recovery_code: 'mfa-code' }
            : { email: 'login-email', password: 'login-password' }
        }
      />
      {error && !Object.keys(error.fieldErrors || {}).length ? <ErrorNotice error={error} /> : null}
      {challenge ? (
        <form onSubmit={submitMfa} className="auth-form">
          <Field
            label={useRecoveryCode ? 'One-time recovery code' : 'Six-digit code'}
            id="mfa-code"
            hint={
              useRecoveryCode
                ? 'Use one unused code saved during staff account setup.'
                : 'Use the current code from your authenticator app.'
            }
            required
          >
            {(props) => (
              <input
                {...props}
                inputMode={useRecoveryCode ? 'text' : 'numeric'}
                autoComplete="one-time-code"
                pattern={useRecoveryCode ? undefined : '[0-9]{6}'}
                maxLength={useRecoveryCode ? 64 : 6}
                value={code}
                onChange={(event) =>
                  setCode(
                    useRecoveryCode ? event.target.value : event.target.value.replace(/\D/g, ''),
                  )
                }
                required
              />
            )}
          </Field>
          <label className="check-field">
            <input
              type="checkbox"
              checked={useRecoveryCode}
              onChange={(event) => {
                setUseRecoveryCode(event.target.checked)
                setCode('')
                setError(null)
              }}
            />
            <span>Use a saved recovery code instead</span>
          </label>
          <Button
            type="submit"
            size="lg"
            loading={loading}
            disabled={useRecoveryCode ? !code.trim() : code.length !== 6}
          >
            Verify and continue <ArrowRight />
          </Button>
          <Button
            variant="text"
            onClick={() => {
              setChallenge(null)
              setCode('')
              setUseRecoveryCode(false)
              setError(null)
            }}
          >
            Use another account
          </Button>
        </form>
      ) : (
        <form onSubmit={submit} className="auth-form">
          <Field label="Email address" id="login-email" required>
            {(props) => (
              <div className="input-with-icon">
                <Mail />
                <input
                  {...props}
                  type="email"
                  autoComplete="email"
                  value={values.email}
                  onChange={(event) =>
                    setValues((value) => ({
                      ...value,
                      email: event.target.value,
                    }))
                  }
                  required
                />
              </div>
            )}
          </Field>
          <Field label="Password" id="login-password" required>
            {(props) => (
              <div className="input-with-icon password-input">
                <LockKeyhole />
                <input
                  {...props}
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  value={values.password}
                  onChange={(event) =>
                    setValues((value) => ({
                      ...value,
                      password: event.target.value,
                    }))
                  }
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((value) => !value)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff /> : <Eye />}
                </button>
              </div>
            )}
          </Field>
          <div className="form-link-row">
            <span /> <Link to="/forgot-password">Forgot password?</Link>
          </div>
          <Button type="submit" size="lg" loading={loading}>
            Sign in <ArrowRight />
          </Button>
          <p className="auth-switch">
            New patient? <Link to="/register">Create an account</Link>
          </p>
          <p className="auth-switch">
            Verification link expired? <Link to="/resend-verification">Request a new link</Link>
          </p>
        </form>
      )}
    </AuthFrame>
  )
}

export function RegisterPage() {
  const brand = useBrand()
  const [values, setValues] = useState({
    full_name: '',
    email: '',
    phone: '',
    date_of_birth: '',
    sex: '',
    address: '',
    password: '',
    password_confirm: '',
    privacy_accepted: false,
  })
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(false)
  const [loading, setLoading] = useState(false)
  const localErrors = useMemo(() => {
    const errors = {}
    if (values.password && values.password.length < 12)
      errors.password = 'Use at least 12 characters.'
    if (values.password_confirm && values.password !== values.password_confirm)
      errors.password_confirm = 'Passwords do not match.'
    return errors
  }, [values.password, values.password_confirm])
  const change = (key) => (event) =>
    setValues((current) => ({
      ...current,
      [key]: event.target.type === 'checkbox' ? event.target.checked : event.target.value,
    }))
  const submit = async (event) => {
    event.preventDefault()
    if (Object.keys(localErrors).length) return
    setLoading(true)
    setError(null)
    const privacyNoticeId = brand.privacy_notice?.id
    if (!privacyNoticeId) {
      setError(
        new Error(
          'Patient registration is not available until the hospital publishes its privacy notice.',
        ),
      )
      setLoading(false)
      return
    }
    const body = patientRegistrationBody(values, privacyNoticeId)
    try {
      await apiRequest('/auth/register/', {
        method: 'POST',
        body,
        idempotent: false,
      })
      setSuccess(true)
    } catch (requestError) {
      setError(requestError)
    } finally {
      setLoading(false)
    }
  }
  return (
    <AuthFrame
      eyebrow="Patient registration"
      title={success ? 'Check your email' : 'Create your patient account'}
      description={
        success
          ? 'If the address can receive mail, a verification message will arrive with the next step.'
          : 'Use your own details. Reception can help if you already have a hospital record.'
      }
      asideTitle="Register once, then manage your own visits"
    >
      {success ? (
        <div className="completion-panel">
          <span className="hero-icon">
            <Mail />
          </span>
          <SuccessNotice>Your registration request was received.</SuccessNotice>
          <p>
            Open the secure verification link in the message. If nothing arrives, wait a few minutes
            before requesting another.
          </p>
          <Link className="button button-primary button-lg" to="/sign-in">
            Return to sign in
          </Link>
        </div>
      ) : (
        <form onSubmit={submit} className="auth-form">
          <ErrorSummary
            errors={{ ...localErrors, ...(error?.fieldErrors || {}) }}
            fieldIds={{
              full_name: 'full-name',
              email: 'register-email',
              phone: 'register-phone',
              date_of_birth: 'date-of-birth',
              sex: 'register-sex',
              address: 'register-address',
              password: 'register-password',
              password_confirm: 'confirm-password',
              privacy_accepted: 'register-privacy',
            }}
          />
          {error && !Object.keys(error.fieldErrors || {}).length ? (
            <ErrorNotice error={error} />
          ) : null}
          <Field label="Full name" id="full-name" error={error?.fieldErrors?.full_name} required>
            {(props) => (
              <input
                {...props}
                autoComplete="name"
                value={values.full_name}
                onChange={change('full_name')}
                required
              />
            )}
          </Field>
          <Field
            label="Email address"
            id="register-email"
            error={error?.fieldErrors?.email}
            required
          >
            {(props) => (
              <input
                {...props}
                type="email"
                autoComplete="email"
                value={values.email}
                onChange={change('email')}
                required
              />
            )}
          </Field>
          <div className="form-grid">
            <Field
              label="Mobile number"
              id="register-phone"
              hint="Use country code, for example +880."
              error={error?.fieldErrors?.phone}
              required
            >
              {(props) => (
                <input
                  {...props}
                  type="tel"
                  autoComplete="tel"
                  pattern="\+[1-9][0-9]{7,14}"
                  value={values.phone}
                  onChange={change('phone')}
                  required
                />
              )}
            </Field>
            <Field
              label="Date of birth"
              id="date-of-birth"
              error={error?.fieldErrors?.date_of_birth}
              required
            >
              {(props) => (
                <input
                  {...props}
                  type="date"
                  autoComplete="bday"
                  max={hospitalDateInputValue()}
                  value={values.date_of_birth}
                  onChange={change('date_of_birth')}
                  required
                />
              )}
            </Field>
          </div>
          <Field label="Sex" id="register-sex" error={error?.fieldErrors?.sex} required>
            {(props) => (
              <select {...props} value={values.sex} onChange={change('sex')} required>
                <option value="">Select</option>
                <option value="female">Female</option>
                <option value="male">Male</option>
                <option value="other">Other</option>
                <option value="unspecified">Prefer not to say</option>
              </select>
            )}
          </Field>
          <Field label="Address" id="register-address" error={error?.fieldErrors?.address} required>
            {(props) => (
              <textarea
                {...props}
                autoComplete="street-address"
                value={values.address}
                onChange={change('address')}
                required
                maxLength="500"
              />
            )}
          </Field>
          <Field
            label="Password"
            id="register-password"
            hint="Use at least 12 characters. A longer phrase is easier to remember."
            error={localErrors.password || error?.fieldErrors?.password}
            required
          >
            {(props) => (
              <input
                {...props}
                type="password"
                autoComplete="new-password"
                minLength="12"
                value={values.password}
                onChange={change('password')}
                required
              />
            )}
          </Field>
          <Field
            label="Confirm password"
            id="confirm-password"
            error={localErrors.password_confirm}
            required
          >
            {(props) => (
              <input
                {...props}
                type="password"
                autoComplete="new-password"
                value={values.password_confirm}
                onChange={change('password_confirm')}
                required
              />
            )}
          </Field>
          <label className="check-field">
            <input
              id="register-privacy"
              type="checkbox"
              checked={values.privacy_accepted}
              onChange={change('privacy_accepted')}
              required
            />
            <span>
              I have read the{' '}
              <Link to="/privacy" target="_blank">
                privacy notice
              </Link>{' '}
              and understand this pilot is not for urgent care.
            </span>
          </label>
          <Button
            type="submit"
            size="lg"
            loading={loading}
            disabled={Object.keys(localErrors).length > 0 || !brand.privacy_notice?.id}
          >
            Create patient account <ArrowRight />
          </Button>
          <p className="auth-switch">
            Already registered? <Link to="/sign-in">Sign in</Link>
          </p>
        </form>
      )}
    </AuthFrame>
  )
}

function AccountEmailPage({ endpoint, eyebrow, title, description, success, buttonLabel }) {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const submit = async (event) => {
    event.preventDefault()
    setLoading(true)
    setError(null)
    try {
      await apiRequest(endpoint, {
        method: 'POST',
        body: { email },
        idempotent: false,
      })
      setSent(true)
    } catch (requestError) {
      setError(requestError)
    } finally {
      setLoading(false)
    }
  }
  return (
    <AuthFrame eyebrow={eyebrow} title={title} description={description}>
      {sent ? (
        <div className="completion-panel">
          <span className="hero-icon">
            <Mail />
          </span>
          <SuccessNotice>{success}</SuccessNotice>
          <Link className="button button-primary button-lg" to="/sign-in">
            Return to sign in
          </Link>
        </div>
      ) : (
        <form className="auth-form" onSubmit={submit}>
          {error ? <ErrorNotice error={error} /> : null}
          <Field label="Email address" id="forgot-email" required>
            {(props) => (
              <input
                {...props}
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            )}
          </Field>
          <Button type="submit" size="lg" loading={loading}>
            {buttonLabel}
          </Button>
          <p className="auth-switch">
            <Link to="/sign-in">Back to sign in</Link>
          </p>
        </form>
      )}
    </AuthFrame>
  )
}

export function ForgotPasswordPage() {
  return (
    <AccountEmailPage
      endpoint="/auth/password/forgot/"
      eyebrow="Account recovery"
      title="Reset your password"
      description="Enter the email used for your account. The response is the same whether or not an account exists."
      success="If the address matches an active account, a reset link will be sent."
      buttonLabel="Send reset link"
    />
  )
}

export function ResendVerificationPage() {
  return (
    <AccountEmailPage
      endpoint="/auth/email/resend/"
      eyebrow="Email verification"
      title="Request a new verification link"
      description="Enter the email used during registration. The response is the same whether or not an eligible account exists."
      success="If the address matches an unverified account, a new verification link will be sent."
      buttonLabel="Send verification link"
    />
  )
}

export function ResetPasswordPage() {
  const [search] = useSearchParams()
  const token = search.get('token') || ''
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [done, setDone] = useState(false)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const submit = async (event) => {
    event.preventDefault()
    if (password !== confirm) return
    setLoading(true)
    setError(null)
    try {
      await apiRequest('/auth/password/reset/', {
        method: 'POST',
        body: { token, password },
        idempotent: false,
      })
      setDone(true)
    } catch (requestError) {
      setError(requestError)
    } finally {
      setLoading(false)
    }
  }
  return (
    <AuthFrame
      eyebrow="Account recovery"
      title={done ? 'Password changed' : 'Choose a new password'}
      description={
        done
          ? 'Existing sessions may have been ended to protect your account.'
          : 'Use a long password that you do not use for another service.'
      }
    >
      {done ? (
        <div className="completion-panel">
          <span className="hero-icon">
            <KeyRound />
          </span>
          <SuccessNotice>Your password was updated.</SuccessNotice>
          <Link className="button button-primary button-lg" to="/sign-in">
            Sign in
          </Link>
        </div>
      ) : (
        <form className="auth-form" onSubmit={submit}>
          {error ? <ErrorNotice error={error} /> : null}
          {!token ? (
            <ErrorNotice error={new Error('This reset link is incomplete. Request a new link.')} />
          ) : null}
          <Field
            label="New password"
            id="new-password"
            error={password && password.length < 12 ? 'Use at least 12 characters.' : ''}
            required
          >
            {(props) => (
              <input
                {...props}
                type="password"
                autoComplete="new-password"
                minLength="12"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            )}
          </Field>
          <Field
            label="Confirm password"
            id="new-password-confirm"
            error={confirm && password !== confirm ? 'Passwords do not match.' : ''}
            required
          >
            {(props) => (
              <input
                {...props}
                type="password"
                autoComplete="new-password"
                value={confirm}
                onChange={(event) => setConfirm(event.target.value)}
                required
              />
            )}
          </Field>
          <Button
            type="submit"
            size="lg"
            loading={loading}
            disabled={!token || password.length < 12 || password !== confirm}
          >
            Change password
          </Button>
        </form>
      )}
    </AuthFrame>
  )
}

export function VerifyEmailPage() {
  const [search] = useSearchParams()
  const token = search.get('token') || ''
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState(null)
  const verify = async () => {
    setStatus('loading')
    setError(null)
    try {
      await apiRequest('/auth/email/verify/', {
        method: 'POST',
        body: { token },
        idempotent: false,
      })
      setStatus('done')
    } catch (requestError) {
      setError(requestError)
      setStatus('error')
    }
  }
  return (
    <AuthFrame
      eyebrow="Email verification"
      title={status === 'done' ? 'Email verified' : 'Confirm your email address'}
      description="This single-use step protects your patient account."
    >
      {status === 'done' ? (
        <div className="completion-panel">
          <span className="hero-icon">
            <CheckCircle2 />
          </span>
          <SuccessNotice>Your email address is verified.</SuccessNotice>
          <Link className="button button-primary button-lg" to="/sign-in">
            Continue to sign in
          </Link>
        </div>
      ) : (
        <div className="auth-form">
          {error ? <ErrorNotice error={error} /> : null}
          {!token ? (
            <ErrorNotice error={new Error('This verification link is incomplete.')} />
          ) : (
            <Button size="lg" loading={status === 'loading'} onClick={verify}>
              Verify email address
            </Button>
          )}
        </div>
      )}
    </AuthFrame>
  )
}

export function AcceptInvitationPage() {
  const [search] = useSearchParams()
  const token = search.get('token') || ''
  const { refreshSession } = useAuth()
  const navigate = useNavigate()
  const [values, setValues] = useState({ display_name: '', password: '', confirm: '' })
  const [enrollment, setEnrollment] = useState(null)
  const [code, setCode] = useState('')
  const [codesAcknowledged, setCodesAcknowledged] = useState(false)
  const [copyStatus, setCopyStatus] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const recoveryCodes = enrollment?.recovery_codes || []

  const accept = async (event) => {
    event.preventDefault()
    if (values.password !== values.confirm) return
    setLoading(true)
    setError(null)
    try {
      const result = await apiRequest('/auth/staff-invitations/accept/', {
        method: 'POST',
        body: staffInvitationAcceptBody(token, values.display_name, values.password),
        idempotent: false,
      })
      setEnrollment(payload(result))
      setValues({ display_name: '', password: '', confirm: '' })
    } catch (requestError) {
      setError(requestError)
    } finally {
      setLoading(false)
    }
  }

  const copyRecoveryCodes = async () => {
    try {
      await navigator.clipboard.writeText(recoveryCodes.join('\n'))
      setCopyStatus('Recovery codes copied. Store them in an approved secure place.')
    } catch {
      setCopyStatus('Copy was unavailable. Select and save the codes manually.')
    }
  }

  const confirmMfa = async (event) => {
    event.preventDefault()
    if (recoveryCodes.length && !codesAcknowledged) return
    setLoading(true)
    setError(null)
    try {
      await apiRequest('/auth/mfa/confirm/', {
        method: 'POST',
        body: { code },
        idempotent: false,
      })
      setEnrollment(null)
      setCode('')
      setCopyStatus('')
      await refreshSession()
      navigate('/app', { replace: true })
    } catch (requestError) {
      setError(requestError)
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthFrame
      eyebrow="Staff invitation"
      title={enrollment ? 'Protect your staff account' : 'Accept your invitation'}
      description={
        enrollment
          ? 'Add this account to an authenticator app, save the one-time recovery codes, then confirm the current code.'
          : 'Create your staff identity using the secure invitation sent by the hospital.'
      }
    >
      <ErrorSummary
        errors={error?.fieldErrors}
        fieldIds={
          enrollment
            ? { code: 'invitation-mfa-code' }
            : {
                display_name: 'invitation-display-name',
                password: 'invitation-password',
                confirm: 'invitation-confirm',
              }
        }
      />
      {error && !Object.keys(error.fieldErrors || {}).length ? <ErrorNotice error={error} /> : null}
      {!token ? (
        <ErrorNotice error={new Error('This invitation link is incomplete.')} />
      ) : enrollment ? (
        <form className="auth-form" onSubmit={confirmMfa}>
          <div className="notice notice-info">
            <ShieldCheck />
            <div>
              <strong>Authenticator setup</strong>
              <p>
                Open this provisioning URI in a compatible authenticator app, or enter the manual
                secret. Do not share either value.
              </p>
              <code className="break-word">{enrollment.provisioning_uri}</code>
              <p>
                <strong>Manual secret:</strong> <code>{enrollment.totp_secret}</code>
              </p>
            </div>
          </div>
          {recoveryCodes.length ? (
            <section className="recovery-code-panel" aria-labelledby="recovery-code-title">
              <h3 id="recovery-code-title">One-time recovery codes</h3>
              <p>
                Save these codes now. Each code works once, and the hospital will not show this set
                again.
              </p>
              <ul>
                {recoveryCodes.map((recoveryCode) => (
                  <li key={recoveryCode}>
                    <code>{recoveryCode}</code>
                  </li>
                ))}
              </ul>
              <Button type="button" variant="secondary" onClick={copyRecoveryCodes}>
                Copy recovery codes
              </Button>
              {copyStatus ? <p role="status">{copyStatus}</p> : null}
              <label className="check-field">
                <input
                  type="checkbox"
                  checked={codesAcknowledged}
                  onChange={(event) => setCodesAcknowledged(event.target.checked)}
                />
                <span>I saved these recovery codes in an approved secure place.</span>
              </label>
            </section>
          ) : null}
          <Field label="Six-digit code" id="invitation-mfa-code" required>
            {(props) => (
              <input
                {...props}
                inputMode="numeric"
                autoComplete="one-time-code"
                pattern="[0-9]{6}"
                maxLength="6"
                value={code}
                onChange={(event) => setCode(event.target.value.replace(/\D/g, ''))}
                required
              />
            )}
          </Field>
          <Button
            type="submit"
            size="lg"
            loading={loading}
            disabled={code.length !== 6 || (recoveryCodes.length > 0 && !codesAcknowledged)}
          >
            Confirm MFA and continue
          </Button>
        </form>
      ) : (
        <form className="auth-form" onSubmit={accept}>
          <Field label="Display name" id="invitation-display-name" required>
            {(props) => (
              <input
                {...props}
                autoComplete="name"
                value={values.display_name}
                onChange={(event) =>
                  setValues((current) => ({ ...current, display_name: event.target.value }))
                }
                required
              />
            )}
          </Field>
          <Field
            label="Password"
            id="invitation-password"
            hint="Use at least 12 characters."
            required
          >
            {(props) => (
              <input
                {...props}
                type="password"
                autoComplete="new-password"
                minLength="12"
                value={values.password}
                onChange={(event) =>
                  setValues((current) => ({ ...current, password: event.target.value }))
                }
                required
              />
            )}
          </Field>
          <Field
            label="Confirm password"
            id="invitation-confirm"
            error={
              values.confirm && values.password !== values.confirm ? 'Passwords do not match.' : ''
            }
            required
          >
            {(props) => (
              <input
                {...props}
                type="password"
                autoComplete="new-password"
                value={values.confirm}
                onChange={(event) =>
                  setValues((current) => ({ ...current, confirm: event.target.value }))
                }
                required
              />
            )}
          </Field>
          <Button
            type="submit"
            size="lg"
            loading={loading}
            disabled={!token || values.password.length < 12 || values.password !== values.confirm}
          >
            Create staff account
          </Button>
        </form>
      )}
    </AuthFrame>
  )
}

export function ClaimAccountPage() {
  const [search] = useSearchParams()
  const token = search.get('token') || ''
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [done, setDone] = useState(false)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const submit = async (event) => {
    event.preventDefault()
    if (password !== confirm) return
    setLoading(true)
    setError(null)
    try {
      await apiRequest('/auth/patient-claims/accept/', {
        method: 'POST',
        body: patientClaimAcceptBody(token, password),
        idempotent: false,
      })
      setDone(true)
      setPassword('')
      setConfirm('')
    } catch (requestError) {
      setError(requestError)
    } finally {
      setLoading(false)
    }
  }
  return (
    <AuthFrame
      eyebrow="Patient account"
      title={done ? 'Account ready' : 'Claim your hospital record'}
      description={
        done
          ? 'Your email is verified and your hospital record is linked.'
          : 'Choose a password to securely access the patient profile reception created for you.'
      }
    >
      <ErrorSummary
        errors={error?.fieldErrors}
        fieldIds={{ password: 'claim-password', token: 'claim-password' }}
      />
      {error && !Object.keys(error.fieldErrors || {}).length ? <ErrorNotice error={error} /> : null}
      {done ? (
        <div className="completion-panel">
          <SuccessNotice>Your patient account is ready.</SuccessNotice>
          <Link className="button button-primary button-lg" to="/sign-in">
            Sign in
          </Link>
        </div>
      ) : (
        <form className="auth-form" onSubmit={submit}>
          {!token ? <ErrorNotice error={new Error('This claim link is incomplete.')} /> : null}
          <Field label="New password" id="claim-password" required>
            {(props) => (
              <input
                {...props}
                type="password"
                minLength="12"
                autoComplete="new-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            )}
          </Field>
          <Field
            label="Confirm password"
            id="claim-password-confirm"
            error={confirm && password !== confirm ? 'Passwords do not match.' : ''}
            required
          >
            {(props) => (
              <input
                {...props}
                type="password"
                autoComplete="new-password"
                value={confirm}
                onChange={(event) => setConfirm(event.target.value)}
                required
              />
            )}
          </Field>
          <Button
            type="submit"
            size="lg"
            loading={loading}
            disabled={!token || password.length < 12 || password !== confirm}
          >
            Claim account
          </Button>
        </form>
      )}
    </AuthFrame>
  )
}

export function StaffSecurityPage() {
  const [currentPassword, setCurrentPassword] = useState('')
  const [enrollment, setEnrollment] = useState(null)
  const [code, setCode] = useState('')
  const [codesAcknowledged, setCodesAcknowledged] = useState(false)
  const [copyStatus, setCopyStatus] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const [complete, setComplete] = useState(false)
  const recoveryCodes = enrollment?.recovery_codes || []

  const start = async (event) => {
    event.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const result = await apiRequest('/auth/mfa/replacement/start/', {
        method: 'POST',
        body: mfaReplacementStartBody(currentPassword),
        idempotent: false,
      })
      setEnrollment(payload(result))
      setCurrentPassword('')
      setComplete(false)
    } catch (requestError) {
      setError(requestError)
    } finally {
      setLoading(false)
    }
  }

  const copyRecoveryCodes = async () => {
    try {
      await navigator.clipboard.writeText(recoveryCodes.join('\n'))
      setCopyStatus('Recovery codes copied. Store them in an approved secure place.')
    } catch {
      setCopyStatus('Copy was unavailable. Select and save the codes manually.')
    }
  }

  const confirm = async (event) => {
    event.preventDefault()
    if (!codesAcknowledged || code.length !== 6) return
    setLoading(true)
    setError(null)
    try {
      await apiRequest('/auth/mfa/replacement/confirm/', {
        method: 'POST',
        body: { code },
        idempotent: false,
      })
      setEnrollment(null)
      setCode('')
      setCodesAcknowledged(false)
      setCopyStatus('')
      setComplete(true)
    } catch (requestError) {
      setError(requestError)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Account protection"
        title="Account security"
        description="Replace your authenticator only while you are signed in and can confirm your current password."
      />
      {complete ? (
        <SuccessNotice>
          Your authenticator and recovery codes were replaced. The previous set no longer works.
        </SuccessNotice>
      ) : null}
      <ErrorSummary
        errors={error?.fieldErrors}
        fieldIds={
          enrollment
            ? { code: 'mfa-replacement-code' }
            : { current_password: 'mfa-replacement-password' }
        }
      />
      {error && !Object.keys(error.fieldErrors || {}).length ? <ErrorNotice error={error} /> : null}
      <Card className="form-card">
        {!enrollment ? (
          <form onSubmit={start}>
            <h2>Replace authenticator</h2>
            <p>
              Use this when changing phones or after signing in with a recovery code. Existing MFA
              remains active until the new code is confirmed.
            </p>
            <Field label="Current password" id="mfa-replacement-password" required>
              {(props) => (
                <input
                  {...props}
                  type="password"
                  autoComplete="current-password"
                  value={currentPassword}
                  onChange={(event) => setCurrentPassword(event.target.value)}
                  required
                />
              )}
            </Field>
            <div className="form-actions">
              <Button type="submit" loading={loading} disabled={!currentPassword}>
                Start secure replacement
              </Button>
            </div>
          </form>
        ) : (
          <form onSubmit={confirm}>
            <h2>Set up the replacement</h2>
            <p>
              Open the provisioning URI in your authenticator app, or enter the manual secret. Do
              not share either value.
            </p>
            <div className="notice notice-info">
              <ShieldCheck aria-hidden="true" />
              <div>
                <strong>Authenticator details</strong>
                <p>
                  <code className="break-word">{enrollment.provisioning_uri}</code>
                </p>
                <p>
                  <strong>Manual secret:</strong> <code>{enrollment.totp_secret}</code>
                </p>
              </div>
            </div>
            <section className="recovery-code-panel" aria-labelledby="replacement-recovery-title">
              <h3 id="replacement-recovery-title">New one-time recovery codes</h3>
              <p>
                Save these now. Each code works once, and this exact set will not be shown again.
              </p>
              <ul>
                {recoveryCodes.map((recoveryCode) => (
                  <li key={recoveryCode}>
                    <code>{recoveryCode}</code>
                  </li>
                ))}
              </ul>
              <Button type="button" variant="secondary" onClick={copyRecoveryCodes}>
                Copy recovery codes
              </Button>
              {copyStatus ? <p role="status">{copyStatus}</p> : null}
              <label className="check-field">
                <input
                  type="checkbox"
                  checked={codesAcknowledged}
                  onChange={(event) => setCodesAcknowledged(event.target.checked)}
                />
                <span>I saved these recovery codes in an approved secure place.</span>
              </label>
            </section>
            <Field
              label="Six-digit code from the new authenticator"
              id="mfa-replacement-code"
              required
            >
              {(props) => (
                <input
                  {...props}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  pattern="[0-9]{6}"
                  maxLength="6"
                  value={code}
                  onChange={(event) => setCode(event.target.value.replace(/\D/g, ''))}
                  required
                />
              )}
            </Field>
            <div className="form-actions">
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setEnrollment(null)
                  setCode('')
                  setCodesAcknowledged(false)
                  setError(null)
                }}
              >
                Cancel replacement
              </Button>
              <Button
                type="submit"
                loading={loading}
                disabled={code.length !== 6 || !codesAcknowledged}
              >
                Confirm replacement
              </Button>
            </div>
          </form>
        )}
      </Card>
    </div>
  )
}
