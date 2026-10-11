import { expect, test } from '@playwright/test'

/**
 * Installing the App is a repository action, and it comes after linking.
 *
 * A connection is attributed to the publisher whose *linked* GitHub login installed it
 * (`connect_repositories`), so the install link is offered once GitHub is linked and
 * nowhere before it. Installing authorizes nothing about the person, which is why the
 * flow that treated it as a sign-in is gone; the link is a plain install page with no
 * state on it.
 */
test('installing the App is offered after linking, and is not a sign-in', async ({
  page,
  request,
}) => {
  expect((await request.post('/api/v1/demo/reset')).ok()).toBe(true)
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))

  await page.goto('/account')
  await page.getByRole('button', { name: 'Demo publisher wallet' }).click()
  await page.getByLabel('Organisation name').fill('Acme Widgets')
  await page.getByRole('button', { name: 'Continue as a publisher' }).click()

  // Before linking: no install link, because that was the step order the flow got wrong.
  await expect(page.getByRole('link', { name: /Install the GitHub App/ })).toHaveCount(0)
  await expect(page.getByText('Link without installing')).toHaveCount(0)

  // Link the account, the way the simulation offers.
  await page.getByLabel('Your GitHub login').fill('acme-widgets')
  await page.getByRole('button', { name: 'Link this login' }).click()
  await expect(page.getByRole('link', { name: 'publisher · acme-widgets' })).toBeVisible()

  // Now the install link is offered, and it is the App's plain install page.
  const install = page.getByRole('link', { name: /Install the GitHub App/ })
  await expect(install).toBeVisible()
  await expect(install).toHaveAttribute(
    'href',
    'https://github.com/apps/misthos-dev/installations/new',
  )

  expect(errors).toEqual([])
})
