from ApiClient import post_json

def get_weather_data_db(layer_type, bounds=None, timestamp=None, use_cache=False, save_cache=True, force_refresh=False, max_age_minutes=60, scenario=None, scenario_id=None):
    """
    Fetch weather data from the database via the /weather/layer endpoint.
    
    Args:
        layer_type (str): 'currents' or 'waves'

        bounds (dict): {north, south, east, west} visible area (optional)
        timestamp (str): ISO formatted datetime string (optional)
        use_cache (bool): Whether to use cached data
        save_cache (bool): Whether to save the result to cache
        force_refresh (bool): Whether to force fetching fresh data
        max_age_minutes (int): Max age of cached data in minutes
        scenario (dict): Scenario configuration (optional)
        scenario_id (int): Scenario ID (optional)

    Returns:
        dict: Weather data response from the API
    """
    if bounds is None:
        # Default bounds (Gulf of Naples/Sorrento area)
        bounds = {
            "north": 40.76,
            "south": 40.50,
            "east": 14.90,
            "west": 14.30
        }
    
    payload = {
        "layer_type": layer_type,
        "bounds": bounds,
        "timestamp": timestamp,
        "use_cache": use_cache,
        "save_cache": save_cache,
        "force_refresh": force_refresh,
        "max_age_minutes": max_age_minutes
    }
    
    if scenario is not None:
        payload["scenario"] = scenario
    if scenario_id is not None:
        payload["scenario_id"] = scenario_id
        
    try:
        # Call the new endpoint
        data = post_json("weather/layer", payload)
        return data
    except Exception as e:
        print(f"[WeatherService] Error fetching data from DB: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
