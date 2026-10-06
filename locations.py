"""Towns the app knows about, and where listings sit on the map."""
import math

# Towns in Botswana, shared by search, filters and the property form
LOCATIONS = [
    'Gaborone', 'Phakalane', 'Francistown', 'Maun', 'Kasane',
    'Serowe', 'Molepolole', 'Kanye', 'Mochudi', 'Lobatse',
    'Palapye', 'Jwaneng', 'Ghanzi', 'Tsabong', 'Letlhakane'
]

# Approximate town-centre coordinates (latitude, longitude) for the map view
TOWN_COORDS = {
    'Gaborone': (-24.6282, 25.9231),
    'Phakalane': (-24.5700, 25.9800),
    'Francistown': (-21.1700, 27.5079),
    'Maun': (-19.9833, 23.4167),
    'Kasane': (-17.7980, 25.1530),
    'Serowe': (-22.3875, 26.7108),
    'Molepolole': (-24.4066, 25.4951),
    'Kanye': (-24.9667, 25.3327),
    'Mochudi': (-24.4167, 26.1500),
    'Lobatse': (-25.2167, 25.6667),
    'Palapye': (-22.5460, 27.1251),
    'Jwaneng': (-24.6017, 24.7281),
    'Ghanzi': (-21.6978, 21.6458),
    'Tsabong': (-26.0500, 22.4500),
    'Letlhakane': (-21.4149, 25.5926),
}

PIN_SPREAD_DEGREES = 0.012  # about 1.3 km between approximate map pins in the same town
MAX_PIN_DISTANCE_KM = 40    # how far a landlord's pin may be from the town they chose


def approximate_position(property_id, town):
    """A stable spot near the town centre for a listing without an exact pin.

    Worked out from the listing's id, so it never moves between visits. Returns
    (latitude, longitude), or None for a town the app has no coordinates for.

    Migration 0003 carries its own copy of this formula; keep the two in step.
    """
    centre = TOWN_COORDS.get(town)
    if not centre or property_id is None:
        return None
    angle = math.radians(property_id * 137.5)            # golden angle keeps neighbours apart
    radius = PIN_SPREAD_DEGREES * math.sqrt(property_id % 12 + 1)
    return (round(centre[0] + radius * math.sin(angle), 5),
            round(centre[1] + radius * math.cos(angle), 5))


def distance_km(a, b):
    """Rough distance between two (latitude, longitude) points. Accurate enough within a town."""
    north = (a[0] - b[0]) * 111.0
    east = (a[1] - b[1]) * 111.0 * math.cos(math.radians((a[0] + b[0]) / 2))
    return math.hypot(north, east)
