let loadPromise: Promise<void> | null = null

export function loadGoogleMaps(): Promise<void> {
  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_BROWSER_API_KEY
  if (!apiKey) return Promise.reject(new Error('VITE_GOOGLE_MAPS_BROWSER_API_KEY is not configured'))
  if ((window as unknown as { google?: { maps?: { importLibrary?: unknown } } }).google?.maps?.importLibrary) return Promise.resolve()
  if (loadPromise) return loadPromise

  loadPromise = new Promise((resolve, reject) => {
    const callback = `__realReviewsGoogleMapsLoaded_${Date.now()}`
    ;(window as unknown as Record<string, () => void>)[callback] = () => {
      delete (window as unknown as Record<string, () => void>)[callback]
      resolve()
    }
    const script = document.createElement('script')
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}&libraries=places&v=weekly&callback=${callback}`
    script.async = true
    script.defer = true
    script.onerror = () => reject(new Error('Failed to load Google Maps JavaScript'))
    document.head.appendChild(script)
  })
  return loadPromise
}
