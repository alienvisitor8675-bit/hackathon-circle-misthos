import { expect, test } from '@playwright/test'

/**
 * Installing the App can be the only GitHub action a publisher takes.
 *
 * The panel that held the install button rendered only once GitHub was already linked
 * — the step installing is meant to replace — so a new publisher saw "Link with
 * GitHub" and never the button that does both. It is offered before linking now, as
 * the primary action, and the install link carries the state that lets the callback
 * finish the link when GitHub sends the install back.
 */
test('a publisher is offered installing the App as the way to link GitHub', async ({
  page,
  request,
}) => {
  expect((await request.post('/api/v1/demo/reset')).ok()).toBe(true)
  const health = await (await request.get('/api/v1/health')).json()
  expect(health.github_oauth).toBe(false) // playwright.config starts the API with no OAuth client
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))

  await page.goto('/account')
  await page.getByRole('button', { name: 'Demo publisher wallet' }).click()
  await page.getByLabel('Organisation name').fill('Acme Widgets')
  await page.getByRole('button', { name: 'Continue as a publisher' }).click()

  const install = page.getByRole('link', { name: 'Install the GitHub App' })
  await expect(install).toBeVisible()
  // The App's install page, carrying the state the callback needs to finish the link.
  await expect(install).toHaveAttribute(
    'href',
    /^https:\/\/github\.com\/apps\/misthos-dev\/installations\/new\?state=.+/,
  )
  // Offered once, as the primary way: the linking panel carries it and the repository
  // panel does not repeat it while GitHub is unlinked.
  await expect(page.getByRole('link', { name: /Install the GitHub App/ })).toHaveCount(1)
  await expect(page.getByText(/Installing the Misthos App on a repository also links/)).toBeVisible()

  expect(errors).toEqual([])
})
