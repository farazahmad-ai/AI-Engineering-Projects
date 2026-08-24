import os
import requests
from urllib.parse import quote

OPENTRIPMAP_KEY = os.getenv("OPENTRIPMAP_API_KEY", "")

# ── Live Weather Tool (Open-Meteo) ────────────────────────────────────────────

WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Icy fog", 51: "Light drizzle", 53: "Moderate drizzle",
    55: "Dense drizzle", 61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail"
}

def _geocode_city(city):
    """Use Open-Meteo geocoding to convert city name → lat/lon."""
    geo_url = (
        f"https://geocoding-api.open-meteo.com/v1/search"
        f"?name={quote(city)}&count=1&language=en&format=json"
    )
    resp = requests.get(geo_url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("results"):
        return None, None, None
    r = data["results"][0]
    return r["latitude"], r["longitude"], r.get("country", "")

def get_live_weather(city: str) -> str:
    """Fetch LIVE real-time weather for any city using Open-Meteo."""
    print(f"LIVE API TOOL: Open-Meteo weather for {city}", flush=True)
    try:
        lat, lon, country = _geocode_city(city)
        if lat is None:
            return f"Could not geocode city: {city}"

        weather_url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code,apparent_temperature"
            f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code"
            f"&forecast_days=5&timezone=auto"
        )
        resp = requests.get(weather_url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        cur = data["current"]
        daily = data["daily"]
        condition = WMO_CODES.get(cur["weather_code"], f"Code {cur['weather_code']}")

        result = (
            f"LIVE weather for {city.title()}, {country} (Open-Meteo):\n"
            f"Right now: {cur['temperature_2m']}°C (feels like {cur['apparent_temperature']}°C), "
            f"{condition}, humidity {cur['relative_humidity_2m']}%, wind {cur['wind_speed_10m']} km/h\n"
            f"5-day forecast:\n"
        )
        for i in range(min(5, len(daily["time"]))):
            day_cond = WMO_CODES.get(daily["weather_code"][i], "Unknown")
            result += (
                f"  {daily['time'][i]}: "
                f"High {daily['temperature_2m_max'][i]}°C / Low {daily['temperature_2m_min'][i]}°C, "
                f"{day_cond}, rain {daily['precipitation_sum'][i]}mm\n"
            )
        return result
    except Exception as e:
        return f"Weather lookup failed: {e}"


# ── Live Attractions Tool (OpenTripMap) ───────────────────────────────────────

ATTRACTION_KINDS = "interesting_places,historic,architecture,museums,natural"

def get_live_attractions(city: str, limit: int = 6) -> str:
    """Fetch LIVE top attractions from OpenTripMap."""
    print(f"LIVE API TOOL: OpenTripMap attractions for {city}", flush=True)

    if not OPENTRIPMAP_KEY:
        return (
            "OpenTripMap API key not set. "
            "Get a free key at https://opentripmap.io/product "
            "and add OPENTRIPMAP_API_KEY to your .env file."
        )

    try:
        BASE = "https://api.opentripmap.com/0.1/en"
        geo = requests.get(
            f"{BASE}/places/geoname",
            params={"name": city, "apikey": OPENTRIPMAP_KEY},
            timeout=10
        ).json()
        lat, lon = geo["lat"], geo["lon"]

        pois = requests.get(
            f"{BASE}/places/radius",
            params={
                "radius": 10000, "lon": lon, "lat": lat,
                "kinds": ATTRACTION_KINDS, "rate": "3",
                "format": "json", "limit": limit,
                "apikey": OPENTRIPMAP_KEY
            },
            timeout=10
        ).json()

        if not pois:
            return f"No top-rated attractions found near {city}."

        result = f"LIVE top attractions near {city.title()} (OpenTripMap):\n"
        for poi in pois[:limit]:
            detail = requests.get(
                f"{BASE}/places/xid/{poi['xid']}",
                params={"apikey": OPENTRIPMAP_KEY},
                timeout=10
            ).json()
            name = detail.get("name", "Unknown")
            kinds = detail.get("kinds", "").replace(",", ", ")
            addr = detail.get("address", {})
            addr_str = ", ".join(filter(None, [addr.get("road", ""), addr.get("suburb", ""), addr.get("city", "")]))
            info = (detail.get("info", {}).get("descr", "") or detail.get("wikipedia_extracts", {}).get("text", ""))
            info = (info[:200].strip() + "...") if info and len(info) > 200 else info

            result += f"\n- {name}"
            if addr_str:
                result += f" ({addr_str})"
            if kinds:
                result += f" | {kinds[:80]}"
            if info:
                result += f"\n  {info}"
        return result

    except Exception as e:
        return f"Attractions lookup failed: {e}"


# ── Live Currency Exchange Rate Tool (Frankfurter API) ────────────────────────

CITY_CURRENCY = {
    "paris": ("EUR", "Euro"), "rome": ("EUR", "Euro"), "barcelona": ("EUR", "Euro"),
    "tokyo": ("JPY", "Japanese Yen"), "bali": ("IDR", "Indonesian Rupiah"),
    "new york": ("USD", "US Dollar"), "london": ("GBP", "British Pound"),
    "dubai": ("AED", "UAE Dirham"), "bangkok": ("THB", "Thai Baht"),
    "sydney": ("AUD", "Australian Dollar"),
}
_SPECIAL_RATES_FROM_USD = {"AED": 3.674, "IDR": 16300}
ECB_CURRENCIES = {"EUR", "JPY", "GBP", "AUD", "THB", "USD"}

def get_live_currency(city: str, from_currency: str = "USD") -> str:
    """Get LIVE exchange rates for a destination city via Frankfurter API."""
    print(f"LIVE API TOOL: Frankfurter currency for {city} from {from_currency}", flush=True)
    try:
        city_lower = city.lower()
        if city_lower not in CITY_CURRENCY:
            return f"Currency info not available for {city}. Supported: {', '.join(CITY_CURRENCY.keys())}"

        to_code, to_name = CITY_CURRENCY[city_lower]

        if to_code not in ECB_CURRENCIES:
            usd_rate = 1.0
            if from_currency != "USD":
                r = requests.get(f"https://api.frankfurter.app/latest?from={from_currency}&to=USD", timeout=10)
                usd_rate = r.json()["rates"]["USD"]
            rate = _SPECIAL_RATES_FROM_USD[to_code] * usd_rate
            return (
                f"Currency for {city.title()} ({to_name}, {to_code}):\n"
                f"1 {from_currency} ≈ {rate:,.2f} {to_code}\n"
                f"(AED is USD-pegged; IDR rate is approximate)"
            )

        base = from_currency if from_currency in ECB_CURRENCIES else "USD"
        target = to_code if to_code != base else "EUR"
        resp = requests.get(f"https://api.frankfurter.app/latest?from={base}&to={target}", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        rate = data["rates"].get(target)
        date = data["date"]

        if rate is None:
            return f"Rate not available for {to_code}"
        if to_code == base:
            rate = 1.0

        return (
            f"LIVE exchange rate for {city.title()} (ECB, as of {date}):\n"
            f"Currency: {to_name} ({to_code})\n"
            f"1 {from_currency} = {rate:,.4f} {to_code}\n"
            f"Common conversions:\n"
            f"  50 {from_currency} = {50*rate:,.2f} {to_code}\n"
            f"  100 {from_currency} = {100*rate:,.2f} {to_code}\n"
            f"  500 {from_currency} = {500*rate:,.2f} {to_code}"
        )
    except Exception as e:
        return f"Currency lookup failed: {e}"
