import { expect, test } from '@playwright/test'
import { mockApi } from './fixtures'

test('opens a local reviewer profile without starting a provider operation', async ({ page }) => {
  await mockApi(page)
  await page.goto('/')
  await page.getByLabel(/free-form restaurant search/i).fill('pizza')
  await page.getByRole('button', { name: 'Go', exact: true }).click()
  await page.getByText(/first noodles/i).first().click()
  await page.getByRole('button', { name: /reviewer with a long display name/i }).click()
  await expect(page).toHaveURL(/\/restaurants\/place-1\?reviewer=reviewer-1&review=review-1/)
  await expect(page.getByText(/second sushi/i)).toBeVisible()
  await expect(page.getByRole('heading', {
    name: 'First Noodles With A Surprisingly Long Mobile Name',
    exact: true
  })).toBeVisible()
  await expect(page.getByRole('heading', { name: /reviewer with a long display name/i })).toBeVisible()
  await expect(page.getByText(/history/i)).toBeVisible()
  await expect(page.getByText(/provider operation/i)).toHaveCount(0)
  await page.goBack()
  await expect(page).toHaveURL(/\/restaurants\/place-1$/)
  await expect(page.getByText(/great outdoor seating/i)).toBeVisible()
  await page.getByRole('button', { name: /reviewer with a long display name/i }).click()
  await page.getByRole('button', { name: /back to reviews/i }).click()
  await expect(page.getByText(/great outdoor seating/i)).toBeVisible()
})

test('restores a direct reviewer URL inside its restaurant workspace', async ({ page }) => {
  await mockApi(page)
  await page.goto('/restaurants/place-1?reviewer=reviewer-1&review=review-1')
  await expect(page.getByRole('heading', { name: 'First Noodles With A Surprisingly Long Mobile Name', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: /reviewer with a long display name/i })).toBeVisible()
})

test('shows broader retained history when the exact restaurant type is empty', async ({ page }) => {
  await mockApi(page, { reviewerContext: 'exact_empty_broader' })
  await page.goto('/restaurants/place-1?reviewer=reviewer-1&review=review-1')

  await expect(page.getByText(/no other tibetan restaurant reviews observed/i)).toBeVisible()
  await expect(page.getByRole('heading', { name: /broader restaurant comparison/i })).toBeVisible()
  await expect(page.getByText(/15 other (restaurants|venues)/i)).toBeVisible()
  await expect(page.getByText(/4\.7 stars/i)).toBeVisible()
  await expect(page.getByRole('heading', { name: /rating overview/i })).toBeVisible()
  await expect(page.getByRole('region', { name: /other tibetan restaurants rating summary/i })).toBeVisible()
  await expect(page.getByRole('region', { name: /broader restaurants rating summary/i })).toBeVisible()
  await expect(page.getByText(/stored review text for the first comparison restaurant/i)).toBeVisible()
  await expect(page.getByText(/showing 5 of 15/i)).toBeVisible()
  await expect(page.getByText(/stored comparison review text 15/i)).toHaveCount(0)
  await page.getByRole('button', { name: /show all 15 reviews/i }).click()
  await expect(page.getByText(/stored comparison review text 15/i)).toBeVisible()
})
