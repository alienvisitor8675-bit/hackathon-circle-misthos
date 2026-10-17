import { expect, type Locator, type Page } from '@playwright/test'

/**
 * Signing in, the one way the app offers it (#181): the landing page's "Sign in" opens
 * the sign-in gate, which asks for a wallet, a GitHub account and a side, in that order,
 * and opens the app at its overview when all three are done.
 *
 * In the simulation the wallet is one of the demo wallets and GitHub is a typed login,
 * because the browser tests run the API without a GitHub OAuth App.
 */

export type Side = 'publisher' | 'contributor'

/** The gate, whichever step it is on: its accessible name is that step's heading. */
export const theGate = (page: Page): Locator => page.getByRole('dialog')

/** Open the gate from the landing page's header. */
export async function openTheGate(page: Page): Promise<Locator> {
  await page.goto('/')
  await page.locator('.site-header').getByRole('button', { name: /Sign in|Finish signing in/ }).click()
  const gate = theGate(page)
  await expect(gate).toBeVisible()
  return gate
}

/** Step 1, with one of the simulation's demo wallets. */
export async function withDemoWallet(gate: Locator, wallet: Side): Promise<void> {
  await expect(gate.getByRole('heading', { name: 'Sign in with your wallet' })).toBeVisible()
  await gate.getByRole('button', { name: `Demo ${wallet} wallet` }).click()
  await expect(gate.getByRole('heading', { name: 'Link your GitHub account' })).toBeVisible()
}

/** Step 2, with a typed login, as the simulation links one without an OAuth App. */
export async function linkLogin(gate: Locator, login: string): Promise<void> {
  await gate.getByLabel('Your GitHub login').fill(login)
  await gate.getByRole('button', { name: 'Link this login' }).click()
  await expect(gate.getByRole('heading', { name: 'Choose your side' })).toBeVisible()
}

/** Step 3. A publisher names its organisation; a contributor is known by its login. */
export async function chooseSide(gate: Locator, side: Side, name?: string): Promise<void> {
  await gate
    .getByLabel(side === 'publisher' ? 'Publisher: I fund fixes' : 'Contributor: I fix issues')
    .check()
  if (side === 'publisher') await gate.getByLabel('Organisation name').fill(name ?? 'Acme')
  await gate.getByRole('button', { name: `Continue as a ${side}` }).click()
}

/** All three steps, from the landing page to the app's overview. */
export async function signInThroughTheGate(
  page: Page,
  side: Side,
  login: string,
  name?: string,
): Promise<void> {
  const gate = await openTheGate(page)
  await withDemoWallet(gate, side)
  await linkLogin(gate, login)
  await chooseSide(gate, side, name)
  await expect(page).toHaveURL(/\/overview$/)
  await expect(theGate(page)).toHaveCount(0)
  await expect(page.getByRole('link', { name: `${side} · ${login}` })).toBeVisible()
}
