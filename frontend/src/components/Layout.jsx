import { useEffect, useState } from 'react'
import { Link, NavLink, Navigate, Outlet, useLocation } from 'react-router-dom'
import {
  Activity,
  Bell,
  Building2,
  CalendarDays,
  ClipboardList,
  ContactRound,
  CreditCard,
  FileClock,
  Home,
  LayoutDashboard,
  LogOut,
  MapPin,
  Menu,
  Search,
  Settings,
  ShieldCheck,
  Stethoscope,
  UserRound,
  UsersRound,
  X,
} from 'lucide-react'
import { Brand } from './Brand'
import { SkipLink } from './SkipLink'
import { Button, ErrorNotice, LoadingState } from './ui'
import { useAuth } from '../context/AuthContext'
import { useBrand } from '../context/BrandContext'

const publicLinks = [
  ['/', 'Home'],
  ['/doctors', 'Find a doctor'],
  ['/about', 'About'],
  ['/contact', 'Contact'],
]

const roleLinks = {
  patient: [
    ['/patient', 'Overview', LayoutDashboard],
    ['/patient/appointments', 'Appointments', CalendarDays],
    ['/patient/notifications', 'Notifications', Bell],
    ['/patient/profile', 'My profile', UserRound],
    ['/patient/privacy', 'Privacy choices', ShieldCheck],
  ],
  doctor: [
    ['/doctor', 'Overview', LayoutDashboard],
    ['/doctor/schedule', 'My schedule', CalendarDays],
    ['/doctor/security', 'Account security', ShieldCheck],
  ],
  receptionist: [
    ['/reception', 'Overview', LayoutDashboard],
    ['/reception/patients', 'Patients', Search],
    ['/reception/appointments', 'Appointments', CalendarDays],
    ['/reception/payments', 'Payments', CreditCard],
    ['/reception/security', 'Account security', ShieldCheck],
  ],
  administrator: [
    ['/admin', 'Overview', LayoutDashboard],
    ['/admin/staff', 'Staff', UsersRound],
    ['/admin/departments', 'Departments', Building2],
    ['/admin/locations', 'Locations', MapPin],
    ['/admin/doctors', 'Doctors', Stethoscope],
    ['/admin/schedules', 'Schedules', CalendarDays],
    ['/admin/notifications', 'Delivery status', Bell],
    ['/admin/audit', 'Audit trail', FileClock],
    ['/admin/settings', 'Settings', Settings],
    ['/admin/security', 'Account security', ShieldCheck],
  ],
}

function bestRole(user) {
  const values = user?.roles || []
  if (values.includes('administrator') || values.includes('admin')) return 'administrator'
  if (values.includes('receptionist')) return 'receptionist'
  if (values.includes('doctor')) return 'doctor'
  if (values.includes('patient')) return 'patient'
  return null
}

export function PublicLayout() {
  const [open, setOpen] = useState(false)
  const { user } = useAuth()
  const role = bestRole(user)
  const dashboard =
    role === 'administrator'
      ? '/admin'
      : role === 'receptionist'
        ? '/reception'
        : role === 'doctor'
          ? '/doctor'
          : role === 'patient'
            ? '/patient'
            : '/not-authorized'
  return (
    <div className="site-frame">
      <SkipLink />
      <header className="public-header">
        <div className="container header-inner">
          <Brand />
          <nav
            id="mobile-nav"
            className={`public-nav ${open ? 'is-open' : ''}`}
            aria-label="Primary navigation"
          >
            {publicLinks.map(([to, label]) => (
              <NavLink key={to} to={to} onClick={() => setOpen(false)}>
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="header-actions">
            {user ? (
              <Link className="button button-primary button-sm" to={dashboard}>
                Open dashboard
              </Link>
            ) : (
              <>
                <Link className="text-link hide-mobile" to="/sign-in">
                  Sign in
                </Link>
                <Link className="button button-primary button-sm" to="/register">
                  Create account
                </Link>
              </>
            )}
            <button
              className="menu-button"
              onClick={() => setOpen((value) => !value)}
              aria-expanded={open}
              aria-controls="mobile-nav"
              aria-label="Toggle navigation"
            >
              {open ? <X /> : <Menu />}
            </button>
          </div>
        </div>
      </header>
      <main id="main-content">
        <Outlet />
      </main>
      <SiteFooter />
    </div>
  )
}

export function SiteFooter() {
  const brand = useBrand()
  return (
    <footer className="site-footer">
      <div className="container footer-grid">
        <div>
          <Brand />
          <p>
            Appointments and queue updates designed around privacy, clarity, and hospital workflow.
          </p>
        </div>
        <div>
          <h2>Service</h2>
          <Link to="/doctors">Find a doctor</Link>
          <Link to="/about">How it works</Link>
          <Link to="/privacy">Privacy notice</Link>
        </div>
        <div>
          <h2>Contact</h2>
          {brand.phone ? (
            <a href={`tel:${brand.phone}`}>{brand.phone}</a>
          ) : (
            <span>Contact details pending hospital approval</span>
          )}
          {brand.email ? <a href={`mailto:${brand.email}`}>{brand.email}</a> : null}
        </div>
      </div>
      <div className="container footer-bottom">
        <span>
          © {new Date().getFullYear()} {brand.name}
        </span>
        <span>Development codename. Hospital branding is configurable.</span>
      </div>
    </footer>
  )
}

export function RequireAuth({ roles }) {
  const { user, status, error, hasRole, refreshSession } = useAuth()
  const location = useLocation()
  if (status === 'loading')
    return (
      <>
        <SkipLink />
        <main id="main-content" className="center-screen">
          <LoadingState label="Checking your secure session" />
        </main>
      </>
    )
  if (status === 'error' && !user)
    return (
      <>
        <SkipLink />
        <main id="main-content" className="center-screen">
          <ErrorNotice
            error={error}
            title="Your session could not be checked"
            onRetry={refreshSession}
          />
        </main>
      </>
    )
  if (!user) return <Navigate to="/sign-in" replace state={{ from: location }} />
  if (!hasRole(roles)) return <Navigate to="/not-authorized" replace />
  return <Outlet />
}

export function AppLayout({ role }) {
  const [open, setOpen] = useState(false)
  const [signOutError, setSignOutError] = useState(null)
  const { user, signOut } = useAuth()
  const canonicalRole = role === 'admin' ? 'administrator' : role
  const links = roleLinks[canonicalRole] || []
  const handleSignOut = async () => {
    setSignOutError(null)
    try {
      await signOut()
    } catch (error) {
      setSignOutError(error)
    }
  }
  return (
    <div className="app-frame">
      <SkipLink />
      <aside id="role-navigation" className={`sidebar ${open ? 'is-open' : ''}`}>
        <div className="sidebar-brand">
          <Brand compact />
          <button
            className="icon-button sidebar-close"
            onClick={() => setOpen(false)}
            aria-label="Close navigation"
          >
            <X />
          </button>
        </div>
        <nav aria-label={`${canonicalRole} navigation`}>
          {links.map(([to, label, Icon]) => (
            <NavLink
              key={to}
              to={to}
              end={to.split('/').length === 2}
              onClick={() => setOpen(false)}
            >
              <Icon aria-hidden="true" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <Link to="/">
            <Home aria-hidden="true" />
            Public website
          </Link>
          <button onClick={handleSignOut}>
            <LogOut aria-hidden="true" />
            Sign out
          </button>
        </div>
      </aside>
      {open ? (
        <button
          className="sidebar-backdrop"
          aria-label="Close navigation"
          onClick={() => setOpen(false)}
        />
      ) : null}
      <div className="app-body">
        <header className="app-header">
          <button
            className="menu-button app-menu"
            onClick={() => setOpen(true)}
            aria-label="Open navigation"
            aria-controls="role-navigation"
            aria-expanded={open}
          >
            <Menu />
          </button>
          <div>
            <p className="eyebrow">Hospital workspace</p>
            <strong>
              {role === 'administrator' ? 'Administration' : role[0].toUpperCase() + role.slice(1)}
            </strong>
          </div>
          <div className="user-chip">
            <span className="avatar" aria-hidden="true">
              {(
                user?.first_name?.[0] ||
                user?.display_name?.[0] ||
                user?.name?.[0] ||
                user?.email?.[0] ||
                'U'
              ).toUpperCase()}
            </span>
            <span>
              <strong>
                {user?.display_name ||
                  user?.full_name ||
                  user?.name ||
                  [user?.first_name, user?.last_name].filter(Boolean).join(' ') ||
                  'Signed in user'}
              </strong>
              <small>{user?.email}</small>
            </span>
          </div>
        </header>
        <main id="main-content" className="app-main">
          {signOutError ? (
            <ErrorNotice error={signOutError} title="Sign out did not finish" />
          ) : null}
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export function RouteFocus() {
  const location = useLocation()
  const [announcement, setAnnouncement] = useState('')
  useEffect(() => {
    const timer = window.setTimeout(() => {
      const main = document.querySelector('#main-content')
      if (!main) return
      if (!main.hasAttribute('tabindex')) main.setAttribute('tabindex', '-1')
      main.focus({ preventScroll: true })
      setAnnouncement(main.querySelector('h1, h2')?.textContent || 'Page changed')
    }, 0)
    return () => window.clearTimeout(timer)
  }, [location.pathname])
  return (
    <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
      {announcement}
    </div>
  )
}

export function RoleHomeRedirect() {
  const { user } = useAuth()
  const role = bestRole(user)
  return (
    <Navigate
      replace
      to={
        role === 'administrator'
          ? '/admin'
          : role === 'receptionist'
            ? '/reception'
            : role === 'doctor'
              ? '/doctor'
              : role === 'patient'
                ? '/patient'
                : '/not-authorized'
      }
    />
  )
}

export function ForbiddenPage() {
  return (
    <>
      <SkipLink />
      <main id="main-content" className="simple-page">
        <div className="simple-panel">
          <span className="hero-icon">
            <ShieldCheck />
          </span>
          <p className="eyebrow">Access restricted</p>
          <h1>This area is not available for your role</h1>
          <p>Your session is active, but this workspace belongs to another hospital role.</p>
          <Link className="button button-primary button-md" to="/app">
            Return to my dashboard
          </Link>
        </div>
      </main>
    </>
  )
}

export function NotFoundPage() {
  return (
    <>
      <SkipLink />
      <main id="main-content" className="simple-page">
        <div className="simple-panel">
          <span className="hero-icon">
            <Activity />
          </span>
          <p className="eyebrow">Page not found</p>
          <h1>We could not find that page</h1>
          <p>The address may have changed or the page may not be available to your account.</p>
          <Link className="button button-primary button-md" to="/">
            Return home
          </Link>
        </div>
      </main>
    </>
  )
}
