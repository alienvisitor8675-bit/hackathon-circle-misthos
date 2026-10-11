import { expect, test } from '@playwright/test'

/**
 * The band is deliberately wide so the buyer picks a position in it.
 *
 * `docs/misthos/06-pricing-engine.md`: "A single point estimate invites a fight over the
 * exact number. A range invites the buyer to pick a position inside it, which is the
 * behaviour we want." The panel offered only the engine's midpoint, so the range was
 * decoration. It takes a price now, and the price it takes is the one committed.
 */
test('a publisher names their own price inside the band, and that is what is committed', async ({
  page,
  request,
}) => {
  expect((await request.post('/api/v1/demo/reset')).ok()).toBe(true)
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))

  await page.goto('/account')
  await page.getByRole('button', { name: 'Demo publisher wallet' }).click()
  await page.getByLabel('Organisation name').fill('Acme Ledger Co')
  await page.getByRole('button', { name: 'Continue as a publisher' }).click()
  await page.getByLabel('GitHub login').fill('acme-ledger')
  await page.getByRole('button', { name: 'Link this login' }).click()

  await page.getByRole('link', { name: 'Publish', exact: true }).click()
  await page.getByLabel('Repository').fill('acme/ledger-core')
  await page.getByLabel('Title').fill('Retry idempotently when settlement returns 503')
  await page.getByRole('button', { name: 'Publish and get a price' }).click()
  await expect(page).toHaveURL(/\/issues\/ISS-\d+$/)

  // The band, as the page shows it, and a position in it that is not the midpoint.
  const band = await page.evaluate(async () => {
    const id = location.pathname.split('/').pop()
    const issue = await (await fetch(`/api/v1/issues/${id}`)).json()
    return issue.proposal as { band_low: { usdc: string }; recommended: { usdc: string } }
  })
  const chosen = band.band_low.usdc
  expect(Number(chosen)).not.toBe(Number(band.recommended.usdc))

  await page.getByRole('button', { name: 'Approve these criteria' }).click()
  await expect(page.getByRole('button', { name: 'Criteria approved' })).toBeVisible()

  const field = page.getByLabel('Your price, in USDC')
  await expect(field).toHaveValue(String(band.recommended.usdc))
  await field.fill(chosen)
  // The button says what it will commit, so the choice is visible before signing.
  await expect(page.getByRole('button', { name: /^Approve the price and commit/ })).toContainText(
    Number(chosen).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  )
  await page.getByRole('button', { name: /^Approve the price and commit/ }).click()

  await expect(page.getByText('Funded and open')).toBeVisible()

  // What the escrow holds and what it will take are the price chosen, not the one the
  // engine recommended: the ceiling is what bounds an agent later.
  const escrow = await page.evaluate(async () => {
    const id = location.pathname.split('/').pop()
    return (await (await fetch(`/api/v1/issues/${id}/escrow`)).json()) as {
      amount: { usdc: string }
      escrow_ceiling: { usdc: string }
    }
  })
  const asShown = Number(chosen).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
  expect(escrow.amount.usdc).toBe(asShown.replace(/,/g, ''))
  expect(escrow.escrow_ceiling.usdc).toBe(asShown.replace(/,/g, ''))
  expect(escrow.escrow_ceiling.usdc).not.toBe(String(band.recommended.usdc))

  expect(errors).toEqual([])
})

test('a price outside the band is refused before anything is signed', async ({ page, request }) => {
  expect((await request.post('/api/v1/demo/reset')).ok()).toBe(true)

  await page.goto('/account')
  await page.getByRole('button', { name: 'Demo publisher wallet' }).click()
  await page.getByLabel('Organisation name').fill('Acme Ledger Co')
  await page.getByRole('button', { name: 'Continue as a publisher' }).click()
  await page.getByLabel('GitHub login').fill('acme-ledger')
  await page.getByRole('button', { name: 'Link this login' }).click()

  await page.getByRole('link', { name: 'Publish', exact: true }).click()
  await page.getByLabel('Repository').fill('acme/ledger-core')
  await page.getByLabel('Title').fill('Retry idempotently when settlement returns 503')
  await page.getByRole('button', { name: 'Publish and get a price' }).click()
  await expect(page).toHaveURL(/\/issues\/ISS-\d+$/)

  await page.getByRole('button', { name: 'Approve these criteria' }).click()
  await page.getByLabel('Your price, in USDC').fill('999999')
  await expect(page.getByText('Outside the band.')).toBeVisible()
  await expect(page.getByRole('button', { name: /^Approve the price and commit/ })).toBeDisabled()
})
