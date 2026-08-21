import { useEffect } from 'react'
import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { BrandProvider } from './context/BrandContext'
import {
  AppLayout,
  ForbiddenPage,
  NotFoundPage,
  PublicLayout,
  RequireAuth,
  RoleHomeRedirect,
  RouteFocus,
} from './components/Layout'
import {
  AboutPage,
  ContactPage,
  DoctorDetailPage,
  DoctorsPage,
  HomePage,
  PrivacyPage,
} from './pages/PublicPages'
import {
  AcceptInvitationPage,
  ClaimAccountPage,
  ForgotPasswordPage,
  RegisterPage,
  ResendVerificationPage,
  ResetPasswordPage,
  SignInPage,
  StaffSecurityPage,
  VerifyEmailPage,
} from './pages/AuthPages'
import {
  AppointmentDetailPage,
  BookingPage,
  NotificationsPage,
  PatientAppointmentsPage,
  PatientDashboard,
  PatientPrivacyPage,
  PatientProfilePage,
  PatientQueuePage,
  RescheduleAppointmentPage,
} from './pages/PatientPages'
import { DoctorDashboard, DoctorQueueConsole, DoctorSchedulePage } from './pages/DoctorPages'
import {
  ReceptionAppointmentsPage,
  ReceptionDashboard,
  ReceptionPatientsPage,
  ReceptionPaymentsPage,
  ReceptionQueuePage,
} from './pages/ReceptionPages'
import {
  AdminAuditPage,
  AdminDashboard,
  AdminNotificationsPage,
  AdminResourcePage,
  AdminSchedulesPage,
  AdminSettingsPage,
  AdminStaffPage,
} from './pages/AdminPages'

function RouteEffects() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'auto' })
  }, [pathname])
  return null
}

export default function App() {
  return (
    <BrowserRouter>
      <BrandProvider>
        <AuthProvider>
          <RouteEffects />
          <RouteFocus />
          <Routes>
            <Route element={<PublicLayout />}>
              <Route index element={<HomePage />} />
              <Route path="doctors" element={<DoctorsPage />} />
              <Route path="doctors/:doctorId" element={<DoctorDetailPage />} />
              <Route path="about" element={<AboutPage />} />
              <Route path="contact" element={<ContactPage />} />
              <Route path="privacy" element={<PrivacyPage />} />
            </Route>
            <Route path="sign-in" element={<SignInPage />} />
            <Route path="register" element={<RegisterPage />} />
            <Route path="verify-email" element={<VerifyEmailPage />} />
            <Route path="resend-verification" element={<ResendVerificationPage />} />
            <Route path="forgot-password" element={<ForgotPasswordPage />} />
            <Route path="reset-password" element={<ResetPasswordPage />} />
            <Route path="accept-invitation" element={<AcceptInvitationPage />} />
            <Route path="claim-account" element={<ClaimAccountPage />} />

            <Route element={<RequireAuth />}>
              <Route path="app" element={<RoleHomeRedirect />} />
            </Route>
            <Route element={<RequireAuth roles={['patient']} />}>
              <Route element={<AppLayout role="patient" />}>
                <Route path="patient" element={<PatientDashboard />} />
                <Route path="patient/appointments" element={<PatientAppointmentsPage />} />
                <Route path="patient/appointments/new" element={<BookingPage />} />
                <Route
                  path="patient/appointments/:appointmentId"
                  element={<AppointmentDetailPage />}
                />
                <Route
                  path="patient/appointments/:appointmentId/reschedule"
                  element={<RescheduleAppointmentPage />}
                />
                <Route path="patient/queue/:queueId" element={<PatientQueuePage />} />
                <Route path="patient/notifications" element={<NotificationsPage />} />
                <Route path="patient/profile" element={<PatientProfilePage />} />
                <Route path="patient/privacy" element={<PatientPrivacyPage />} />
              </Route>
            </Route>

            <Route element={<RequireAuth roles={['doctor']} />}>
              <Route element={<AppLayout role="doctor" />}>
                <Route path="doctor" element={<DoctorDashboard />} />
                <Route path="doctor/schedule" element={<DoctorSchedulePage />} />
                <Route path="doctor/security" element={<StaffSecurityPage />} />
                <Route path="doctor/queue/:queueId" element={<DoctorQueueConsole />} />
              </Route>
            </Route>

            <Route element={<RequireAuth roles={['receptionist']} />}>
              <Route element={<AppLayout role="receptionist" />}>
                <Route path="reception" element={<ReceptionDashboard />} />
                <Route path="reception/patients" element={<ReceptionPatientsPage />} />
                <Route path="reception/appointments" element={<ReceptionAppointmentsPage />} />
                <Route
                  path="reception/appointments/:appointmentId/reschedule"
                  element={
                    <RescheduleAppointmentPage
                      backTo="/reception/appointments"
                      completeTo="/reception/appointments"
                    />
                  }
                />
                <Route path="reception/queues/:queueId" element={<ReceptionQueuePage />} />
                <Route path="reception/payments" element={<ReceptionPaymentsPage />} />
                <Route path="reception/security" element={<StaffSecurityPage />} />
              </Route>
            </Route>

            <Route element={<RequireAuth roles={['administrator', 'admin']} />}>
              <Route element={<AppLayout role="administrator" />}>
                <Route path="admin" element={<AdminDashboard />} />
                <Route path="admin/staff" element={<AdminStaffPage />} />
                <Route
                  path="admin/departments"
                  element={<AdminResourcePage type="departments" />}
                />
                <Route path="admin/locations" element={<AdminResourcePage type="locations" />} />
                <Route path="admin/doctors" element={<AdminResourcePage type="doctors" />} />
                <Route path="admin/schedules" element={<AdminSchedulesPage />} />
                <Route path="admin/notifications" element={<AdminNotificationsPage />} />
                <Route path="admin/audit" element={<AdminAuditPage />} />
                <Route path="admin/settings" element={<AdminSettingsPage />} />
                <Route path="admin/security" element={<StaffSecurityPage />} />
              </Route>
            </Route>

            <Route path="not-authorized" element={<ForbiddenPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </AuthProvider>
      </BrandProvider>
    </BrowserRouter>
  )
}
