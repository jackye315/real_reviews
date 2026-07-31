import { expect, test } from '@playwright/test'
import { mockApi } from './fixtures'

test('mobile WebKit can search, open reviews, use filter sheet, and return to results', async ({ page }) => {
  await mockApi(page)
  await page.goto('/')

  await page.getByLabel(/free-form restaurant search/i).fill('sushi')
  await page.getByRole('button', { name: 'Go', exact: true }).click()
  await expect(page.getByText(/first noodles/i)).toBeVisible()

  await page.getByText(/first noodles/i).first().click()
  await expect(page.getByRole('button', { name: /filters/i })).toBeVisible()
  await page.getByRole('button', { name: /filters/i }).click()
  await expect(page.getByRole('dialog', { name: /review filters/i })).toBeVisible()
  await page.getByRole('button', { name: /done/i }).click()

  await page.getByRole('button', { name: /results/i }).click()
  await expect(page.getByText(/second sushi/i)).toBeVisible()
})
