import { expect, test } from '@playwright/test'
import { mockApi } from './fixtures'

test('appends a saved review page without starting a provider operation', async ({ page }) => {
  await mockApi(page)
  await page.goto('/')
  await page.getByLabel(/free-form restaurant search/i).fill('noodles')
  await page.getByRole('button', { name: 'Go', exact: true }).click()
  await page.getByText(/First Noodles With/).click()
  await expect(page.getByText(/Show more saved reviews/i)).toBeVisible()
  await page.getByRole('button', { name: /Show more saved reviews/i }).click()
  await expect(page.getByText('Older saved review.')).toBeVisible()
})
