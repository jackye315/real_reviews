import { useEffect, useRef, useState } from 'react'
import { loadGoogleMaps } from '../lib/googleMaps'

type Props = {
  onSelected: (selection: {
    google_place_id: string
    display_name: string
    formatted_address?: string | null
    location?: { latitude: number; longitude: number } | null
    viewport?: Record<string, unknown> | null
    place_types?: string[]
    google_maps_url?: string | null
  }) => void
}

type GooglePlaceWithFetch = google.maps.places.Place & {
  fetchFields: (options: { fields: string[] }) => Promise<void>
}

type PlaceAutocompleteElement = HTMLElement & {
  locationBias?: google.maps.Circle | { center: google.maps.LatLngLiteral; radius: number }
}

export function Autocomplete({ onSelected }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [status, setStatus] = useState('Loading Google Places autocomplete…')
  const [locationStatus, setLocationStatus] = useState('Location improves nearby suggestions. Your coordinates stay in browser memory only.')

  useEffect(() => {
    let disposed = false
    async function setup() {
      try {
        await loadGoogleMaps()
        await google.maps.importLibrary('places')
        if (disposed || !containerRef.current) return
        const element = new google.maps.places.PlaceAutocompleteElement() as PlaceAutocompleteElement
        element.className = 'block w-full rounded-xl border border-[#CFC6BA] bg-[#FFFDFC] px-3 py-2 text-[#24313A] shadow-sm'
        element.style.colorScheme = 'light'
        element.style.setProperty('--md-sys-color-surface', '#FFFDFC')
        element.style.setProperty('--md-sys-color-on-surface', '#24313A')
        element.style.setProperty('--md-sys-color-on-surface-variant', '#6B7378')
        element.style.setProperty('--md-sys-color-primary', '#B7462D')
        element.setAttribute('aria-label', 'Search for a restaurant or location')
        containerRef.current.replaceChildren(element)
        setStatus('')

        navigator.geolocation?.getCurrentPosition(
          (position) => {
            element.locationBias = {
              center: {
                lat: position.coords.latitude,
                lng: position.coords.longitude
              },
              radius: 8047
            }
            setLocationStatus('Using an in-memory 5 mile location bias for suggestions.')
          },
          () => setLocationStatus('Location unavailable or denied. Google IP-based bias will be used.'),
          { enableHighAccuracy: false, timeout: 5000, maximumAge: 300000 }
        )

        element.addEventListener('gmp-select', async (event: Event) => {
          try {
            setStatus('Loading selected place details…')
            const placePrediction =
              (event as google.maps.places.PlacePredictionSelectEvent).placePrediction ??
              (event as CustomEvent).detail?.placePrediction
            if (!placePrediction) {
              setStatus('Google did not return a place prediction for that selection.')
              return
            }
            const place = placePrediction.toPlace() as GooglePlaceWithFetch
            await place.fetchFields({ fields: ['id', 'formattedAddress', 'location', 'viewport', 'types'] })
            if (!place.id) {
              setStatus('Google did not return a Place ID for that selection.')
              return
            }
            const location = place.location
              ? { latitude: place.location.lat(), longitude: place.location.lng() }
              : null
            setStatus('Saving selected place…')
            onSelected({
              google_place_id: place.id,
              display_name: placePrediction.text?.toString() ?? place.id ?? 'Selected place',
              formatted_address: place.formattedAddress ?? null,
              location,
              viewport: place.viewport?.toJSON() as Record<string, unknown> | undefined,
              place_types: place.types ?? [],
              google_maps_url: `https://www.google.com/maps/place/?q=place_id:${encodeURIComponent(place.id)}`
            })
            setStatus('')
          } catch (error) {
            setStatus(error instanceof Error ? `Place selection failed: ${error.message}` : 'Place selection failed.')
          }
        })
      } catch (error) {
        setStatus(error instanceof Error ? error.message : 'Google autocomplete failed to load.')
      }
    }
    setup()
    return () => {
      disposed = true
    }
  }, [onSelected])

  return (
    <div className="space-y-2">
      <p className="text-sm text-[#4B5A63]">{locationStatus}</p>
      <div ref={containerRef} />
      {status && <p className="text-sm text-[#B7462D]">{status}</p>}
    </div>
  )
}
