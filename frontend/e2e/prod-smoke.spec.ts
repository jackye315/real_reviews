import { expect, test, type Response } from '@playwright/test'

// Regression guard for the PRODUCTION frontend image (static nginx + baked
// bundle). The dev Vite server has no CSP and injects VITE_* at runtime, so
// it cannot catch the prod-only failures this spec targets:
//   - the served Content-Security-Policy blocking Google Maps fonts / icons /
//     the Places autocomplete API
//   - the VITE_GOOGLE_MAPS_BROWSER_API_KEY not being baked into the bundle
// Run against the built production frontend (PROD_SMOKE=1):
//   PROD_SMOKE=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:8080 \
//     pnpm exec playwright test --project=prod-smoke
test.skip(
  process.env.PROD_SMOKE !== '1',
  'prod-smoke only runs against the production frontend (set PROD_SMOKE=1)'
)

// Every Google Maps origin the autocomplete widget needs. The CSP must
// explicitly allow each of these or prod autocomplete silently breaks.
const CSP_REQUIRED_ORIGINS = [
  'https://fonts.googleapis.com', // Google Maps fonts (style-src)
  'https://maps.gstatic.com', // map files / autocomplete popup icons (img-src, connect-src)
  'https://places.googleapis.com', // Places autocomplete RPC (connect-src)
  'https://fonts.gstatic.com' // font files (font-src)
]

test('served CSP allows Google Maps resources and autocomplete fires requests', async ({ page }) => {
  const cspViolations: string[] = []
  const autocompleteRequests: string[] = []

  page.on('console', (msg) => {
    if (/Content Security Policy/i.test(msg.text())) cspViolations.push(msg.text())
  })
  page.on('request', (req) => {
    if (req.url().includes('AutocompletePlaces')) autocompleteRequests.push(req.url())
  })

  const response: Response | null = await page.goto('/')
  expect(response?.ok()).toBeTruthy()

  // The served CSP must include every required origin. Tightening any of
  // these re-breaks prod autocomplete (fonts/icons/API blocked by CSP).
  const csp = response?.headers()['content-security-policy'] ?? ''
  expect(csp, 'a Content-Security-Policy header should be present').not.toBe('')
  for (const origin of CSP_REQUIRED_ORIGINS) {
    expect(csp, `CSP must allow ${origin}`).toContain(origin)
  }

  await expect(page.getByRole('heading', { name: /find a restaurant/i })).toBeVisible()

  // Type into the Google autocomplete widget; it must issue Places RPCs.
  const widget = page.locator('gmp-place-autocomplete')
  await expect(widget).toHaveCount(1)
  await widget.first().click()
  await page.keyboard.type('starbucks', { delay: 120 })

  await expect
    .poll(() => autocompleteRequests.length, {
      timeout: 15000,
      message: 'expected an AutocompletePlaces request to be sent'
    })
    .toBeGreaterThan(0)

  // The widget's suggestion popup renders in a closed shadow root Playwright
  // cannot inspect, so CSP violations in the console are the regression signal.
  expect(cspViolations).toEqual([])
})