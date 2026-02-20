
import math
import datetime
import numpy as np
import pandas as pd
import xarray as xr
import copernicusmarine

class WeatherService:
    def __init__(self):
        # TODO: Replace with your actual Copernicus Marine credentials
        self.username = "sriccardi"
        self.password = "Napoli1926"
        # Force login on first use (or when credentials change)
        self._logged_in = False

    def _ensure_login(self):
        if not self._logged_in:
            try:
                # Login to Copernicus Marine Service
                copernicusmarine.login(
                    username=self.username,
                    password=self.password,
                    force_overwrite=True
                )
                self._logged_in = True
            except Exception as e:
                print(f"[WeatherService] Login failed: {e}")

    def get_data(self, layer_type, bounds=None, timestamp=None):
        """
        Fetch weather data based on layer_type from Copernicus Marine Service.
        
        Args:
            layer_type (str): 'currents' or 'waves'
            bounds (dict): {north, south, east, west} visible area (optional)
            timestamp (str): ISO formatted datetime string (optional)

        Returns:
            dict: {timestamp: str, items: list}
        """
        self._ensure_login()

        # Define dataset IDs and variable mappings
        if layer_type == 'currents':
            dataset_id = "cmems_mod_med_phy-cur_anfc_4.2km_PT15M-i"
            # Map backend variables to our output keys
            req_vars = ["uo", "vo"]
        elif layer_type == 'waves':
            dataset_id = "cmems_mod_med_wav_anfc_4.2km_PT1H-i"
            # Map backend variables to our output keys
            # Note: Verify specific variable names in the dataset, usually standard like:
            # VMDR: Mean wave direction to (or from? usually 'from' for wind/waves)
            # VTM01: Mean wave period
            # VHM0: Significant wave height
            req_vars = ["VMDR_WW", "VTM01_WW", "VHM0_WW"]
        else:
            return []

        try:
            # Open dataset (lazy loading)
            ds = copernicusmarine.open_dataset(
                dataset_id=dataset_id,
                username=self.username,
                password=self.password,
            )
            
            # Select time slice
            if timestamp:
                try:
                    target_time = pd.to_datetime(timestamp)
                    print(f"[WeatherService] Using requested timestamp: {target_time}")
                except Exception as e:
                    print(f"[WeatherService] Invalid timestamp '{timestamp}': {e}. Using current time.")
                    target_time = datetime.datetime.now()
            else:
                target_time = datetime.datetime.now()

            try:
                ds_slice = ds.sel(time=target_time, method='nearest')
            except KeyError:
                 # fallback if time is out of range
                 print(f"[WeatherService] Time {target_time} out of range. Using last available time.")
                 ds_slice = ds.isel(time=-1)

            # Spatial subsetting if bounds are provided
            # Copernicus MED datasets usually have lat between 30 and 46, lon -6 to 37
            if bounds:
                # Add buffer
                pad = 0.05
                lat_min = bounds.get('south', 40.50) - pad
                lat_max = bounds.get('north', 40.76) + pad
                lon_min = bounds.get('west', 14.30) - pad
                lon_max = bounds.get('east', 14.90) + pad
            else:
                # Default bounds (Gulf of Naples/Sorrento area) as requested
                lat_min = 40.50
                lat_max = 40.76
                lon_min = 14.30
                lon_max = 14.90

            # Handle possible 0-360 vs -180-180 logic (MED is usually standard -180 to 180)
            ds_slice = ds_slice.sel(
                latitude=slice(lat_min, lat_max), 
                longitude=slice(lon_min, lon_max)
            )

            # Subsampling for performance
            # Use step=1 for maximum resolution (4.2km) as requested
            step = 1 
            ds_slice = ds_slice.isel(
                latitude=slice(0, None, step), 
                longitude=slice(0, None, step)
            )


            # Load into DataFrame (reset_index converts coords to columns)
            # Use specific variables to avoid loading unnecessary data
            ds_slice = ds_slice[req_vars]
            df = ds_slice.to_dataframe().dropna().reset_index()
            
            # Get the actual time of the data slice
            # Assuming 'time' is a scalar coordinate after selection
            data_time = "?"
            if 'time' in ds_slice.coords:
                dt_val = ds_slice.time.values
                # Convert numpy.datetime64 to readable string
                data_time = str(np.datetime_as_string(dt_val, unit='m'))
            
            # Filter exactly within the requested bounds (pandas filtering)

            lat_req_min, lat_req_max = 40.52, 40.80
            lon_req_min, lon_req_max = 14.30, 14.90
            
            # Determine column names dynamically
            lat_col = 'latitude' if 'latitude' in df.columns else 'lat'
            lon_col = 'longitude' if 'longitude' in df.columns else 'lon'
            
            # Apply precise masking
            df = df[
                (df[lat_col] >= lat_req_min) & (df[lat_col] <= lat_req_max) &
                (df[lon_col] >= lon_req_min) & (df[lon_col] <= lon_req_max)
            ]
            
            # Debug: print columns to see correct names
            print(f"[WeatherService] Dataframe columns: {df.columns.tolist()}")
            
            # Calculate min/max magnitude for visualization scaling
            val_min = 0.0
            val_max = 1.0
            
            if layer_type == 'currents':
                # Magnitude = sqrt(u^2 + v^2)
                mags = np.sqrt(df['uo']**2 + df['vo']**2)
                if not mags.empty:
                    val_min = float(mags.min())
                    val_max = float(mags.max())
            elif layer_type == 'waves':
                # Use Wave Height (VHM0_WW) for scaling
                if 'VHM0_WW' in df.columns and not df.empty:
                    val_min = float(df['VHM0_WW'].min())
                    val_max = float(df['VHM0_WW'].max())

            data = []
            
            # Helper to get value from row regardless of column name (lat vs latitude)
            def get_val(row, keys):
                for k in keys:
                    if hasattr(row, k):
                        return getattr(row, k)
                return 0.0

            # Iterate and format
            # Use 'itertuples' for faster iteration than 'iterrows'
            if layer_type == 'currents':
                for row in df.itertuples():
                    data.append({
                        'lat': float(get_val(row, ['lat', 'latitude'])),
                        'lon': float(get_val(row, ['lon', 'longitude'])),
                        'u': float(row.uo), # Eastward
                        'v': float(row.vo)  # Northward
                    })
            elif layer_type == 'waves':
                for row in df.itertuples():
                    # Handle potential missing vars just in case, though dropna already run
                    if hasattr(row, 'VMDR_WW') and hasattr(row, 'VHM0_WW') and hasattr(row, 'VTM01_WW'):
                        data.append({
                            'lat': float(get_val(row, ['lat', 'latitude'])),
                            'lon': float(get_val(row, ['lon', 'longitude'])),
                            'dir': float(row.VMDR_WW),
                            'height': float(row.VHM0_WW),
                            'period': float(row.VTM01_WW)
                        })

            ds.close()
            # Check if this return object still matches QWebChannel slot signature
            return {
                "timestamp": data_time.replace('T', ' '),
                "dataset": dataset_id,
                "items": data,
                "range": {"min": val_min, "max": val_max}
            }

        except Exception as e:
            print(f"[WeatherService] Error fetching data for {layer_type}: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e)}




weather_service = WeatherService()
