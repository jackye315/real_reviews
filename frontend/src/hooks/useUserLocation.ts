import { useEffect, useState } from 'react'

export type BrowserLocation = { latitude: number; longitude: number }

export function useUserLocation() {
  const [userLocation, setUserLocation] = useState<BrowserLocation | null>(null)

  useEffect(() => {
    navigator.geolocation?.getCurrentPosition(
      (position) => {
        setUserLocation({ latitude: position.coords.latitude, longitude: position.coords.longitude })
      },
      () => setUserLocation(null),
      { enableHighAccuracy: false, timeout: 5000, maximumAge: 300000 }
    )
  }, [])

  return userLocation
}
