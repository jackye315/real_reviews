import { defineConfig, devices } from '@playwright/test'

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? 'http://127.0.0.1:5173'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['list']] : 'list',
  use: {
    baseURL,
    trace: 'on-first-retry'
  },
  projects: [
    {
      name: 'chromium-phone-portrait',
      testMatch: /responsive\.spec\.ts/,
      use: { ...devices['Pixel 5'], browserName: 'chromium', viewport: { width: 390, height: 844 } }
    },
    {
      name: 'chromium-phone-landscape',
      testMatch: /responsive\.spec\.ts/,
      use: { browserName: 'chromium', viewport: { width: 844, height: 390 }, isMobile: true }
    },
    {
      name: 'chromium-tablet-portrait',
      testMatch: /responsive\.spec\.ts/,
      use: { browserName: 'chromium', viewport: { width: 768, height: 1024 }, isMobile: true }
    },
    {
      name: 'chromium-desktop',
      testMatch: /responsive\.spec\.ts/,
      use: { browserName: 'chromium', viewport: { width: 1280, height: 800 } }
    },
    {
      name: 'webkit-mobile-smoke',
      testMatch: /webkit-smoke\.spec\.ts/,
      use: { ...devices['iPhone 12'], browserName: 'webkit', viewport: { width: 390, height: 844 } }
    }
  ]
})
