"""
Canonical list of tracked municipalities. Imported everywhere so we never
have to update this list in more than one place.

Sauganash is a Chicago neighborhood, not a separate municipality. Tax/court
records will show it as "Chicago" but the user may want to filter for it.
"""

TRACKED_CITIES = [
    "Chicago",
    "Lincolnwood",
    "Sauganash",
    "Skokie",
    "Evanston",
]

# Uppercased copies used by SoQL queries against Cook County (their `city`
# field is uppercased).
TRACKED_CITIES_UPPER = [c.upper() for c in TRACKED_CITIES]
