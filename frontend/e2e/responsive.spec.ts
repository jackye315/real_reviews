import { expect, test } from '@playwright/test'
import { mockApi } from './fixtures'

test.beforeEach(async ({ page }) => {
  await mockApi(page)
})

test('landing, results, reviews, filters, and back navigation avoid horizontal overflow', async ({ page }, testInfo) => {
  const isDesktop = testInfo.project.name.includes('desktop')
  await page.goto('/')
  await expect(page.getByRole('heading', { name: /find a restaurant/i })).toBeVisible()
  await expectNoHorizontalOverflow(page)

  await page.getByLabel(/free-form restaurant search/i).fill('sushi')
  await page.getByRole('button', { name: 'Go', exact: true }).click()
  await expect(page.getByText(/first noodles/i)).toBeVisible()
  await expectNoHorizontalOverflow(page)

  await page.getByText(/first noodles/i).first().click()
  const reviewPane = page.locator('section').filter({ hasText: /great outdoor seating/i }).last()
  await expect(reviewPane.getByText(/123 very long address/i)).toBeVisible()
  await expect(reviewPane.getByText(/great outdoor seating/i)).toBeVisible()
  await expect(reviewPane.getByLabel('Review details')).toBeVisible()
  await expect(reviewPane.getByLabel('5 out of 5 stars')).toHaveText('5 ★★★★★')
  await expectReviewGalleryOverflowContained(reviewPane)
  await expectNoHorizontalOverflow(page)

  if (isDesktop) {
    await expect(page.getByLabel(/exact rating/i)).toBeVisible()
    await expect(page.getByRole('button', { name: /^filter$/i })).toBeVisible()
  } else {
    await expect(page.getByRole('button', { name: /filters/i })).toBeVisible()
    await expect(page.getByRole('dialog', { name: /review filters/i })).toHaveCount(0)
    await page.getByRole('button', { name: /filters/i }).click()
    const filterDialog = page.getByRole('dialog', { name: /review filters/i })
    await expect(filterDialog).toBeVisible()
    await expect(filterDialog.getByLabel(/exact rating/i)).toBeVisible()
    await filterDialog.getByLabel(/exact rating/i).selectOption('5')
    await filterDialog.getByRole('button', { name: /done/i }).click()
    await expect(page.getByRole('dialog', { name: /review filters/i })).toBeHidden()
    await page.getByRole('button', { name: /results/i }).click()
    await expect(page.getByText(/second sushi/i)).toBeVisible()
  }

  await expectNoHorizontalOverflow(page)
})

test('manifest and mobile metadata are available', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('link[rel="manifest"]')).toHaveAttribute('href', '/manifest.webmanifest')
  await expect(page.locator('link[rel="apple-touch-icon"]')).toHaveAttribute('href', '/icons/apple-touch-icon.png')
  await expect(page.locator('meta[name="theme-color"]')).toHaveAttribute('content', '#B7462D')

  const manifest = await page.request.get('/manifest.webmanifest')
  expect(manifest.ok()).toBeTruthy()
  const body = await manifest.json()
  expect(body.name).toBe('Real Reviews')
  expect(body.display).toBe('standalone')
  expect(body.start_url).toBe('/')
})

async function expectNoHorizontalOverflow(page: import('@playwright/test').Page) {
  await expect.poll(async () => page.evaluate(() => (
    document.documentElement.scrollWidth <= window.innerWidth
    && Array.from(document.querySelectorAll<HTMLElement>('[data-testid="review-pane"]'))
      .every((pane) => pane.scrollWidth <= pane.clientWidth)
  ))).toBe(true)
}

async function expectReviewGalleryOverflowContained(reviewPane: import('@playwright/test').Locator) {
  const card = reviewPane.getByRole('article')
  const photoStrip = reviewPane.getByTestId('review-photo-strip')
  await expect(photoStrip.getByRole('img')).toHaveCount(7)
  await expect.poll(async () => card.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true)
  await expect.poll(async () => photoStrip.evaluate((element) => element.scrollWidth > element.clientWidth)).toBe(true)
}
