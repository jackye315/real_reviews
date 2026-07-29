from app.utils.geo import distance_meters


def test_distance_meters_returns_expected_order_of_magnitude():
    # Approximate distance between Times Square and Empire State Building.
    distance = distance_meters(40.7580, -73.9855, 40.7484, -73.9857)
    assert 900 <= distance <= 1200
