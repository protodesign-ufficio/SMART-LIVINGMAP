"""utils.py
Utility helpers used by the application.

Currently contains a Python implementation of the color hashing function
used in the web map to keep colors consistent across Python and JS.
"""

def color_from_string_py(s: str) -> str:
    """Return a hex color string derived from the provided string.

    This replicates the JavaScript `colorFromString` hashing function so
    that Python can compute the same default color as the map code.

    Returns '#0077be' for empty or '__gps' keys.
    """
    if not s:
        return '#0077be'
    if s == '__gps':
        return '#0077be'
    h = 0
    for ch in s:
        h = ((h << 5) - h) + ord(ch)
        h &= 0xFFFFFFFF
    hexv = (h >> 0) & 0xFFFFFF
    return f"#{hexv:06x}"
