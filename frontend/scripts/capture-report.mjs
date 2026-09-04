import { createHmac } from 'node:crypto'
import path from 'node:path'
import { chromium } from '@playwright/test'

const BASE_URL = process.env.REPORT_BASE_URL || 'http://localhost:8081'
const OUTPUT = path.resolve(process.cwd(), '../report_assets/screenshots')
const PASSWORD = 'SyntheticOnly!2026'

function decodeBase32(value) {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'
  let bits = ''
  for (const character of value.replace(/=+$/, '').toUpperCase()) {
    bits += alphabet.indexOf(character).toString(2).padStart(5, '0')
  }
  const bytes = []
  for (let offset = 0; offset + 8 <= bits.length; offset += 8) {
    bytes.push(Number.parseInt(bits.slice(offset, offset + 8), 2))
  }
  return Buffer.from(bytes)
}

function currentTotp(secret) {
  const counter = BigInt(Math.floor(Date.now() / 30_000))
  const message = Buffer.alloc(8)
  message.writeBigUInt64BE(counter)
  const digest = createHmac('sha1', decodeBase32(secret)).update(message).digest()
  const offset = digest[digest.length - 1] & 0x0f
  const number =
    (((digest[offset] & 0x7f) << 24) |
      ((digest[offset + 1] & 0xff) << 16) |
      ((digest[offset + 2] & 0xff) << 8) |
      (digest[offset + 3] & 0xff)) %
    1_000_000
  return String(number).padStart(6, '0')
}

async function signIn(page, email, secret = '') {
  await page.goto(`${BASE_URL}/sign-in`)
  await page.locator('#login-email').fill(email)
  await page.locator('#login-password').fill(PASSWORD)
  await page.getByRole('button', { name: /^Sign in/ }).click()
  if (secret) {
    await page.getByRole('heading', { name: 'Enter your verification code' }).waitFor()
    await page.locator('#mfa-code').fill(currentTotp(secret))
    await page.getByRole('button', { name: /Verify and continue/ }).click()
  }
  await page.locator('#main-content h1').first().waitFor()
}

async function capture(page, fileName) {
  await page.waitForTimeout(350)
  await page.screenshot({ path: path.join(OUTPUT, fileName), fullPage: false })
}

async function workspace(browser, email, secret = '') {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    colorScheme: 'light',
    locale: 'en-GB',
    timezoneId: 'Asia/Dhaka',
  })
  const page = await context.newPage()
  const failures = []
  page.on('pageerror', (event) => failures.push(`Page error: ${event.message}`))
  page.on('console', (event) => {
    if (event.type() === 'error') failures.push(`Console error: ${event.text()}`)
  })
  page.on('response', (response) => {
    if (response.status() >= 500)
      failures.push(`Server error: ${response.status()} ${response.url()}`)
  })
  await signIn(page, email, secret)
  return { context, page, failures }
}

const browser = await chromium.launch({ headless: true })

const publicContext = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
const publicPage = await publicContext.newPage()
await publicPage.goto(BASE_URL)
await publicPage.getByRole('heading', { name: /Your visit should begin with clarity/ }).waitFor()
await capture(publicPage, '01-public-home.png')
await publicPage.goto(`${BASE_URL}/doctors`)
await publicPage.getByRole('heading', { name: 'Find a doctor' }).waitFor()
await capture(publicPage, '02-doctor-directory.png')
await publicContext.close()

const patient = await workspace(browser, 'patient.demo@example.test')
await capture(patient.page, '03-patient-dashboard.png')
await patient.page.goto(`${BASE_URL}/patient/appointments/new`)
await patient.page.getByRole('heading', { name: 'Book an appointment' }).waitFor()
await capture(patient.page, '04-appointment-booking.png')
await patient.page.getByRole('button', { name: 'Open help assistant' }).click()
await patient.page
  .getByLabel('Ask about this hospital system')
  .fill('Is Dr Farhana Rahman available tomorrow?')
await patient.page.getByRole('button', { name: 'Send question' }).click()
await patient.page.getByText('Live hospital data').waitFor()
await capture(patient.page, '05-patient-assistant-live-availability.png')
await patient.context.close()

const reception = await workspace(browser, 'reception.demo@example.test', 'KRSXG5DSNFXGOIDB')
await capture(reception.page, '06-reception-dashboard.png')
await reception.page.goto(`${BASE_URL}/reception/appointments`)
await reception.page.getByLabel('Find appointment').fill('Ayesha Rahman')
await reception.page.getByRole('button', { name: 'Search', exact: true }).click()
const appointmentRow = reception.page.getByRole('row', { name: /Ayesha Rahman/ })
await appointmentRow.waitFor()
const checkInButton = appointmentRow.getByRole('button', { name: 'Check in' })
if (await checkInButton.isVisible().catch(() => false)) {
  await checkInButton.click()
  await reception.page.getByText(/Checked in\. Queue token/).waitFor()
}
await capture(reception.page, '07-reception-checked-in-appointment.png')
await reception.context.close()

const doctor = await workspace(browser, 'doctor01@example.test', 'JBSWY3DPEHPK3PXP')
await capture(doctor.page, '08-doctor-dashboard.png')
await doctor.page.getByRole('button', { name: 'Open help assistant' }).click()
await doctor.page
  .getByLabel('Ask about this hospital system')
  .fill('When is my patient pressure lowest this week?')
await doctor.page.getByRole('button', { name: 'Send question' }).click()
await doctor.page.getByText('Live hospital data').waitFor()
await capture(doctor.page, '09-doctor-assistant-workload.png')
await doctor.page.getByRole('button', { name: 'Close help assistant' }).last().click()
await doctor.page.locator('.queue-list a').first().click()
await doctor.page.getByText('Doctor queue console').waitFor()
const callNext = doctor.page.getByRole('button', { name: 'Call next patient' })
if (await callNext.isVisible().catch(() => false)) {
  await callNext.click()
  await doctor.page.getByText('Called', { exact: true }).first().waitFor()
}
await capture(doctor.page, '10-doctor-queue-called-patient.png')
await doctor.context.close()

const queuePatient = await workspace(browser, 'patient.demo@example.test')
await queuePatient.page.getByRole('link', { name: 'View details', exact: true }).first().click()
await queuePatient.page.getByRole('link', { name: /Open live queue/ }).click()
await queuePatient.page.getByRole('heading', { name: 'Your visit progress' }).waitFor()
await capture(queuePatient.page, '11-patient-live-queue-called.png')
await queuePatient.context.close()

const admin = await workspace(browser, 'admin.demo@example.test', 'MFRGGZDFMZTWQ2LK')
await capture(admin.page, '12-administrator-dashboard.png')
await admin.page.goto(`${BASE_URL}/admin/schedules`)
await admin.page.locator('#main-content h1').first().waitFor()
await capture(admin.page, '13-administrator-schedules.png')
await admin.page.goto(`${BASE_URL}/admin/audit`)
await admin.page.locator('#main-content h1').first().waitFor()
await capture(admin.page, '14-administrator-audit-trail.png')
await admin.page.getByRole('button', { name: 'Open help assistant' }).click()
await admin.page
  .getByLabel('Ask about this hospital system')
  .fill("Give me today's operational summary")
await admin.page.getByRole('button', { name: 'Send question' }).click()
await admin.page.getByText('Live hospital data').waitFor()
await capture(admin.page, '15-administrator-assistant-summary.png')
await admin.context.close()

const allFailures = [patient, reception, doctor, queuePatient, admin].flatMap(
  (item) => item.failures,
)
await browser.close()

if (allFailures.length) {
  throw new Error(allFailures.join('\n'))
}

console.log(`Captured 15 report screenshots in ${OUTPUT}`)
/* global Buffer, console, process */
