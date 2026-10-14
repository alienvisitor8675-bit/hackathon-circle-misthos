import { expect, test } from '@playwright/test'

/**
 * The overview describes the deployment it is actually looking at.
 *
 * It used to say "Simulated build … the money is fake and no chain is contacted"
 * whatever the deployment was, and offer Reset simulation on a live one where reset is
 * refused and there is nothing to reset. Both now follow the API's own answer.
 *
 * This suite runs the API simulated, so it pins that branch; the live branch is the
 * same two expressions with `simulated` false, verified against the deployment.
 */
test('the overview follows what the API reports about the deployment', async ({ page, request }) => {
  const health = await (await request.get('/api/v1/health')).json()
  expect(health.simulated).toBe(true) // playwright.config starts the API simulated

  await page.goto('/overview')
  await expect(page.getByRole('button', { name: 'Reset simulation' })).toBeVisible()
  const banner = page.locator('.banner').first()
  await expect(banner).toContainText('Simulated build')
  await expect(banner).toContainText('GitHub is simulated until a GitHub App is configured')
  await expect(banner).not.toContainText('Live on')
})
