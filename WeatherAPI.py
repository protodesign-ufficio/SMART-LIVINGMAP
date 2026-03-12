"""Client per recuperare i dati meteo (onde e correnti) dal backend.

Fornisce due funzioni:
- `get_weather_layer`: recupera i dati meteo per un layer (onde/correnti) specificando bounds e timestamp.
- `get_weather_layer_from_cache`: recupera i dati meteo da una cache key.
"""

try:
    from ApiClient import post_json, get_json
except Exception:
    try:
        from project.ApiClient import post_json, get_json
    except Exception:
        post_json = None
        get_json = None


def get_weather_layer(layer_type, bounds, timestamp,
                      use_cache=True, save_cache=True,
                      force_refresh=False, max_age_minutes=15):
    """Recupera i dati meteo dal backend tramite POST a /weather/layer/.

    Args:
        layer_type: 'waves' o 'currents'.
        bounds: dict con chiavi 'north', 'south', 'east', 'west'.
        timestamp: stringa ISO del timestamp richiesto.
        use_cache: se usare la cache.
        save_cache: se salvare in cache.
        force_refresh: se forzare il refresh.
        max_age_minutes: età massima della cache in minuti.

    Returns:
        dict con i dati meteo (items, range, timestamp, ecc.).
    """
    if post_json is None:
        raise RuntimeError('Client API non disponibile')

    payload = {
        "layer_type": layer_type,
        "bounds": bounds,
        "timestamp": timestamp,
        "use_cache": use_cache,
        "save_cache": save_cache,
        "force_refresh": force_refresh,
        "max_age_minutes": max_age_minutes,
    }
    return post_json('weather/layer/', payload=payload)


def get_weather_layer_from_cache(cache_key):
    """Recupera i dati meteo dalla cache tramite GET a /weather/cache/layer/{cache_key}.

    Args:
        cache_key: chiave di cache restituita dall'endpoint di dettaglio percorso.

    Returns:
        dict con i dati meteo (items, range, timestamp, ecc.).
    """
    if get_json is None:
        raise RuntimeError('Client API non disponibile')

    return get_json(f'weather/cache/layer/{cache_key}')
