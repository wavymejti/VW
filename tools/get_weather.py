import requests
from datetime import datetime

def get_weather_forecast(lat, lng, date_str=None):
    """
    Fetch weather forecast for a specific location and date.
    Uses Open-Meteo (free, no key required).
    
    Args:
        lat (float): Latitude.
        lng (float): Longitude.
        date_str (str, optional): YYYY-MM-DD. If None, returns current forecast.
        
    Returns:
        dict: Weather summary or error.
    """
    try:
        # Base URL for Open-Meteo
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lng,
            "daily": "weathercode,temperature_2m_max,temperature_2m_min",
            "timezone": "auto"
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if "daily" not in data:
            return {"status": "error", "message": "Invalid weather data"}
            
        daily = data["daily"]
        
        # If specific date requested, find it
        if date_str and date_str in daily["time"]:
            idx = daily["time"].index(date_str)
            return {
                "status": "success",
                "date": date_str,
                "weather_code": daily["weathercode"][idx],
                "temp_max": daily["temperature_2m_max"][idx],
                "temp_min": daily["temperature_2m_min"][idx],
                "description": _map_weather_code(daily["weathercode"][idx])
            }
        
        # Otherwise return current (first day)
        return {
            "status": "success",
            "date": daily["time"][0],
            "weather_code": daily["weathercode"][0],
            "temp_max": daily["temperature_2m_max"][0],
            "temp_min": daily["temperature_2m_min"][0],
            "description": _map_weather_code(daily["weathercode"][0])
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

def _map_weather_code(code):
    """Map WMO weather codes to human descriptions."""
    codes = {
        0: "Clear sky ☀️",
        1: "Mainly clear 🌤️", 2: "Partly cloudy ⛅", 3: "Overcast ☁️",
        45: "Foggy 🌫️", 48: "Depositing rime fog 🌫️",
        51: "Light drizzle 🌧️", 53: "Moderate drizzle 🌧️", 55: "Dense drizzle 🌧️",
        61: "Slight rain 🌦️", 63: "Moderate rain 🌧️", 65: "Heavy rain 🌧️",
        71: "Slight snow 🌨️", 73: "Moderate snow 🌨️", 75: "Heavy snow 🌨️",
        80: "Slight rain showers 🌦️", 81: "Moderate rain showers 🌦️", 82: "Violent rain showers 🌧️",
        95: "Thunderstorm ⛈️", 96: "Thunderstorm with slight hail ⛈️", 99: "Thunderstorm with heavy hail ⛈️"
    }
    return codes.get(code, "Unknown ❓")

if __name__ == "__main__":
    # Test: Munich weather
    print(get_weather_forecast(48.1351, 11.5820))
