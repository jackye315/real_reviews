declare namespace google.maps.places {
  class PlaceAutocompleteElement extends HTMLElement {
    locationBias?: google.maps.Circle | { center: google.maps.LatLngLiteral; radius: number }
  }
}
