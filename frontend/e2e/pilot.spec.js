import { createHmac } from 'node:crypto'
import { expect, test } from '@playwright/test'

const PASSWORD = 'SyntheticOnly!2026'

function decodeBase32(value) {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'
  let bits = ''
  for (const character of value.replace(/=+$/, '').toUpperCase()) {
    const index = alphabet.indexOf(character)
    if (index < 0) throw new Error('Invalid synthetic TOTP secret')
    bits += index.toString(2).padStart(5, '0')
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

async function signIn(page, email, totpSecret = '') {
  await page.goto('/sign-in')
  await page.locator('#login-email').fill(email)
  await page.locator('#login-password').fill(PASSWORD)
  await page.getByRole('button', { name: /^Sign in/ }).click()
  if (totpSecret) {
    await expect(page.getByRole('heading', { name: 'Enter your verification code' })).toBeVisible()
    await page.locator('#mfa-code').fill(currentTotp(totpSecret))
    await page.getByRole('button', { name: /Verify and continue/ }).click()
    await page.waitForURL(email.startsWith('reception.') ? /\/reception/ : /\/doctor/)
  } else {
    await page.waitForURL(/\/patient/)
  }
}

test.describe.serial('production pilot browser flows', () => {
  test('public service and approved privacy notice load at the same origin', async ({ page }) => {
    await page.goto('/')
    await expect(
      page.getByRole('heading', { name: /Your visit should begin with clarity/ }),
    ).toBeVisible()
    await expect(page.getByRole('link', { name: 'Skip to main content' })).toHaveCount(1)
    await page.getByRole('link', { name: 'Privacy notice' }).first().click()
    await expect(
      page.getByRole('heading', { name: 'Synthetic demonstration privacy notice' }),
    ).toBeVisible()
  })

  test('patient can sign in and inspect real schedule availability', async ({ page }) => {
    await signIn(page, 'patient.demo@example.test')
    await page.goto('/patient/appointments/new')
    await expect(page.getByRole('heading', { name: 'Book an appointment' })).toBeVisible()
    await page.getByText('Dr Synthetic 01', { exact: true }).click()
    await page.getByRole('button', { name: /Continue/ }).click()

    const date = page.getByLabel('Appointment date')
    const current = await date.inputValue()
    const tomorrow = new Date(`${current}T00:00:00Z`)
    tomorrow.setUTCDate(tomorrow.getUTCDate() + 1)
    await date.fill(tomorrow.toISOString().slice(0, 10))
    await expect(
      page.getByRole('radiogroup', { name: 'Available appointment times' }),
    ).toBeVisible()
    await expect(page.getByRole('radio').first()).toBeEnabled()
  })

  test('receptionist completes MFA and checks in the synthetic patient', async ({ page }) => {
    await signIn(page, 'reception.demo@example.test', 'KRSXG5DSNFXGOIDB')
    await expect(page.getByRole('heading', { name: 'Today at reception' })).toBeVisible()
    await page.getByRole('link', { name: 'Appointments', exact: true }).click()
    await page.getByLabel('Find appointment').fill('Synthetic Patient 0001')
    await page.getByRole('button', { name: 'Search', exact: true }).click()

    const row = page.getByRole('row', { name: /Synthetic Patient 0001/ })
    await expect(row).toBeVisible()
    await row.getByRole('button', { name: 'Check in' }).click()
    await expect(page.getByText(/Checked in\. Queue token/)).toBeVisible()
  })

  test('patient sees only a token and non-sensitive location guidance', async ({ page }) => {
    await signIn(page, 'patient.demo@example.test')
    await page.goto('/patient/appointments')
    await page.getByRole('link', { name: /View appointment with Dr Synthetic 01/ }).click()
    const snapshotResponse = page.waitForResponse(
      (response) => response.url().includes('/queues/') && response.url().endsWith('/snapshot/'),
    )
    await page.getByRole('link', { name: /Open live queue/ }).click()
    const snapshot = await (await snapshotResponse).json()

    await expect(page.getByRole('heading', { name: 'Your visit progress' })).toBeVisible()
    await expect(page.getByText('Where to go')).toBeVisible()
    await expect(page.getByText(/Dr Synthetic 01.*Main Building.*Chamber 01/)).toBeVisible()
    expect(JSON.stringify(snapshot)).not.toMatch(
      /patient_name|full_name|date_of_birth|phone|email/i,
    )
    await expect(page.getByText('Synthetic Patient 0002')).toHaveCount(0)
  })

  test('assigned doctor completes MFA and opens the operational queue', async ({ page }) => {
    await signIn(page, 'doctor01@example.test', 'JBSWY3DPEHPK3PXP')
    await expect(page.getByRole('heading', { name: 'Today’s overview' })).toBeVisible()
    const queueLink = page.locator('.queue-list a').first()
    await expect(queueLink).toBeVisible()
    await queueLink.click()
    await expect(page.getByText('Doctor queue console')).toBeVisible()
    await expect(page.getByText(/Operational first in, first out order/)).toBeVisible()
  })
})
