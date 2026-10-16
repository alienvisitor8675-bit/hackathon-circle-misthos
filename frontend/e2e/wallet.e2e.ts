import { expect, test } from '@playwright/test'
import { chooseSide, linkLogin, openTheGate } from './gate'

/**
 * The wallet a party signs in with is the wallet its money moves through (#29, #181).
 *
 * A Circle wallet is a way in rather than a second wallet set up afterwards, so the
 * profile names the wallet signed in with and offers no other. In the simulation
 * Circle's frame never opens; on Arc the same button runs the PIN challenge first.
 */
test('the wallet signed in with is the one the money moves through', async ({ page, request }) => {
  expect((await request.post('/api/v1/demo/reset')).ok()).toBe(true)
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))

  const gate = await openTheGate(page)
  await gate.getByRole('button', { name: 'Sign in with a Circle wallet' }).click()
  await linkLogin(gate, 'wallet-tester')
  await chooseSide(gate, 'contributor')
  await expect(page).toHaveURL(/\/overview$/)

  const me = await (await page.request.get('/api/v1/auth/me')).json()
  await page.goto('/account')
  await expect(page.getByText('Your payouts are released to the wallet you signed in with.')).toBeVisible()
  await expect(page.getByTitle(me.address)).toBeVisible()
  // One wallet, so no panel offers to set up another.
  await expect(page.getByRole('button', { name: 'Set up or reconnect your wallet' })).toHaveCount(0)

  expect(errors).toEqual([])
})
