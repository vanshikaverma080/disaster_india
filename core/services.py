import os, sys, heapq, math, requests
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path
from django.conf import settings
from django.core.cache import cache
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier

# Dashboard district coordinates are local so the first page render does not
# fan out to geocoding/weather/hazard APIs for every district.
DISTRICT_SEEDS = [
    ("Delhi", "Delhi"), ("Mumbai", "Maharashtra"), ("Pune", "Maharashtra"),
    ("Ahmedabad", "Gujarat"), ("Surat", "Gujarat"), ("Jaipur", "Rajasthan"),
    ("Lucknow", "Uttar Pradesh"), ("Kanpur", "Uttar Pradesh"), ("Varanasi", "Uttar Pradesh"),
    ("Prayagraj", "Uttar Pradesh"), ("Patna", "Bihar"), ("Gaya", "Bihar"),
    ("Kolkata", "West Bengal"), ("Bhubaneswar", "Odisha"), ("Guwahati", "Assam"),
    ("Ranchi", "Jharkhand"), ("Bhopal", "Madhya Pradesh"), ("Indore", "Madhya Pradesh"),
    ("Nagpur", "Maharashtra"), ("Hyderabad", "Telangana"), ("Bengaluru", "Karnataka"),
    ("Chennai", "Tamil Nadu"), ("Kochi", "Kerala"), ("Thiruvananthapuram", "Kerala"),
    ("Visakhapatnam", "Andhra Pradesh"), ("Vijayawada", "Andhra Pradesh"),
    ("Bhubaneswar", "Odisha"), ("Srinagar", "Jammu and Kashmir"), ("Dehradun", "Uttarakhand"),
    ("Shimla", "Himachal Pradesh"), ("Chandigarh", "Chandigarh"), ("Panaji", "Goa"),
    ("Gurugram", "Haryana"), ("Panipat", "Haryana"), ("Amritsar", "Punjab"),
    ("Jodhpur", "Rajasthan"), ("Kota", "Rajasthan"), ("Raipur", "Chhattisgarh"),
]

DISTRICT_COORDS = {
    "Delhi": (28.6139, 77.2090), "Mumbai": (19.0760, 72.8777), "Pune": (18.5204, 73.8567),
    "Ahmedabad": (23.0225, 72.5714), "Surat": (21.1702, 72.8311), "Jaipur": (26.9124, 75.7873),
    "Lucknow": (26.8467, 80.9462), "Kanpur": (26.4499, 80.3319), "Varanasi": (25.3176, 82.9739),
    "Prayagraj": (25.4358, 81.8463), "Patna": (25.5941, 85.1376), "Gaya": (24.7914, 85.0002),
    "Kolkata": (22.5726, 88.3639), "Bhubaneswar": (20.2961, 85.8245), "Guwahati": (26.1445, 91.7362),
    "Ranchi": (23.3441, 85.3096), "Bhopal": (23.2599, 77.4126), "Indore": (22.7196, 75.8577),
    "Nagpur": (21.1458, 79.0882), "Hyderabad": (17.3850, 78.4867), "Bengaluru": (12.9716, 77.5946),
    "Chennai": (13.0827, 80.2707), "Kochi": (9.9312, 76.2673), "Thiruvananthapuram": (8.5241, 76.9366),
    "Visakhapatnam": (17.6868, 83.2185), "Vijayawada": (16.5062, 80.6480),
    "Srinagar": (34.0837, 74.7973), "Dehradun": (30.3165, 78.0322), "Shimla": (31.1048, 77.1734),
    "Chandigarh": (30.7333, 76.7794), "Panaji": (15.4909, 73.8278), "Gurugram": (28.4595, 77.0266),
    "Panipat": (29.3909, 76.9635), "Amritsar": (31.6340, 74.8723), "Jodhpur": (26.2389, 73.0243),
    "Kota": (25.2138, 75.8648), "Raipur": (21.2514, 81.6296),
}

_GEO_CACHE = {}
_MODEL = None
BASE_DIR = Path(__file__).resolve().parent.parent
HISTORICAL_CSV = BASE_DIR / "data" / "historical" / "historical_disasters.csv"
SHELTERS_CSV = BASE_DIR / "data" / "static" / "shelters.csv"
HOSPITALS_CSV = BASE_DIR / "data" / "static" / "hospitals.csv"


def _cache_key(prefix, *parts):
    safe = [str(x).strip().lower().replace(" ", "_") for x in parts]
    return "climateguard:" + prefix + ":" + ":".join(safe)


def _cached(key, builder, timeout=None):
    cached = cache.get(key)
    if cached is not None:
        if isinstance(cached, dict):
            return {**cached, "cached": True}
        return cached
    data = builder()
    cache.set(key, data, timeout or settings.LIVE_API_CACHE_SECONDS)
    if isinstance(data, dict):
        return {**data, "cached": False}
    return data


def _timeout(default=None):
    return default or settings.LIVE_API_TIMEOUT_SECONDS


@lru_cache(maxsize=1)
def historical_events():
    if not HISTORICAL_CSV.exists():
        return pd.DataFrame()
    df = pd.read_csv(HISTORICAL_CSV)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["month"] = df["date"].dt.month.fillna(6).astype(int)
    df["severity_weight"] = df["severity"].map({"LOW": 0.25, "MEDIUM": 0.5, "HIGH": 0.75, "CRITICAL": 1.0}).fillna(0.5)
    return df


def historical_profile(district_name):
    df = historical_events()
    if df.empty:
        return {"events": 0, "flood_events": 0, "flood_prior": 0.28, "common_hazards": []}
    rows = df[df["district"].str.lower() == str(district_name).lower()]
    if rows.empty:
        state = next((state for name, state in DISTRICT_SEEDS if name.lower() == str(district_name).lower()), "")
        rows = df[df["state"].str.lower() == state.lower()] if state else rows
    if rows.empty:
        return {"events": 0, "flood_events": 0, "flood_prior": 0.28, "common_hazards": []}
    flood_rows = rows[rows["disaster_type"].str.lower().isin(["flood", "cyclone"])]
    event_pressure = min(len(flood_rows) / max(len(rows), 1), 1)
    severity_pressure = float(flood_rows["severity_weight"].mean()) if not flood_rows.empty else 0.25
    flood_prior = round(min(0.9, 0.18 + 0.48 * event_pressure + 0.22 * severity_pressure), 3)
    hazards = rows["disaster_type"].value_counts().head(3).index.tolist()
    return {
        "events": int(len(rows)),
        "flood_events": int(len(flood_rows)),
        "flood_prior": flood_prior,
        "common_hazards": hazards,
    }


def historical_hazard_profile(name, state):
    df = historical_events()
    hazards = {
        "flood": {"types": {"flood", "cyclone"}, "prior": 0.0, "events": 0, "driver": "No local historical flood events in bundled data"},
        "earthquake": {"types": {"earthquake"}, "prior": 0.0, "events": 0, "driver": "No local historical earthquake events in bundled data"},
        "fire": {"types": {"wildfire", "heatwave"}, "prior": 0.0, "events": 0, "driver": "No local historical fire/heat events in bundled data"},
        "sealevel": {"types": {"cyclone", "flood"}, "prior": 0.0, "events": 0, "driver": "No coastal/sea-level history in bundled data"},
    }
    if df.empty:
        return hazards
    local = df[df["district"].str.lower() == name.lower()].copy()
    state_rows = df[df["state"].str.lower() == state.lower()].copy()
    for hazard, meta in hazards.items():
        local_rows = local[local["disaster_type"].str.lower().isin(meta["types"])]
        state_hazard_rows = state_rows[state_rows["disaster_type"].str.lower().isin(meta["types"])]
        source_rows = local_rows if not local_rows.empty else state_hazard_rows
        if source_rows.empty:
            continue
        event_score = min(len(source_rows) / 4, 1)
        severity_score = float(source_rows["severity_weight"].mean())
        population_score = min(float(source_rows["affected_population"].mean()) / 150000, 1)
        prior = round(min(0.35, 0.16 * event_score + 0.13 * severity_score + 0.06 * population_score), 3)
        label = "local" if not local_rows.empty else "state"
        top_type = source_rows["disaster_type"].value_counts().index[0]
        hazards[hazard].update({
            "prior": prior,
            "events": int(len(source_rows)),
            "driver": f"{label.title()} {top_type.lower()} history: {len(source_rows)} event(s), average severity {source_rows['severity'].mode().iat[0]}",
        })
    return hazards


@lru_cache(maxsize=1)
def _resource_rows():
    shelters = pd.read_csv(SHELTERS_CSV).to_dict("records") if SHELTERS_CSV.exists() else []
    hospitals = pd.read_csv(HOSPITALS_CSV).to_dict("records") if HOSPITALS_CSV.exists() else []
    return shelters, hospitals


def _geo(name):
    key = name.strip().lower()
    if key in _GEO_CACHE:
        return _GEO_CACHE[key]
    for seed_name, state in DISTRICT_SEEDS:
        if seed_name.lower() == key:
            lat, lng = DISTRICT_COORDS[seed_name]
            d = {"name": seed_name, "state": state, "lat": lat, "lng": lng, "country": "India"}
            _GEO_CACHE[key] = d
            return d
    r = requests.get("https://geocoding-api.open-meteo.com/v1/search", params={
        "name": name, "count": 1, "language": "en", "format": "json", "countryCode": "IN"
    }, timeout=_timeout())
    r.raise_for_status()
    results = r.json().get("results") or []
    if not results:
        raise ValueError(f"Location not found: {name}")
    x = results[0]
    d = {"name": x.get("name", name), "state": x.get("admin1", "India"),
         "lat": float(x["latitude"]), "lng": float(x["longitude"]), "country": x.get("country", "India")}
    _GEO_CACHE[key] = d
    return d


def _baseline_risks(name, state, lat, lng):
    coastal = {"Mumbai", "Surat", "Kolkata", "Bhubaneswar", "Chennai", "Kochi",
               "Thiruvananthapuram", "Visakhapatnam", "Panaji"}
    flood_states = {"Bihar", "Uttar Pradesh", "Assam", "West Bengal", "Odisha", "Kerala"}
    quake_states = {"Jammu and Kashmir", "Uttarakhand", "Himachal Pradesh", "Assam", "Gujarat"}
    dry_states = {"Rajasthan", "Gujarat", "Madhya Pradesh", "Chhattisgarh"}
    history = historical_hazard_profile(name, state)
    flood = 0.24 + (0.16 if state in flood_states else 0) + (0.07 if name in coastal else 0) + history["flood"]["prior"]
    earthquake = 0.14 + (0.24 if state in quake_states else 0) + history["earthquake"]["prior"]
    fire = 0.18 + (0.16 if state in dry_states else 0) + (0.05 if lat < 19 else 0) + history["fire"]["prior"]
    sealevel = (0.34 if name in coastal else 0.02) + (0.10 if name in coastal else 0) * min(history["sealevel"]["events"], 2)
    risks = {
        "flood": round(min(flood, 0.88), 3),
        "earthquake": round(min(earthquake, 0.82), 3),
        "fire": round(min(fire, 0.80), 3),
        "sealevel": round(min(sealevel, 0.72), 3),
    }
    drivers = {
        "flood": history["flood"]["driver"] if history["flood"]["events"] else ("Coastal flood/cyclone exposure" if name in coastal else f"{state} monsoon basin exposure" if state in flood_states else "Lower baseline flood exposure"),
        "earthquake": history["earthquake"]["driver"] if history["earthquake"]["events"] else (f"{state} seismic-zone exposure" if state in quake_states else "Lower baseline seismic exposure"),
        "fire": history["fire"]["driver"] if history["fire"]["events"] else (f"{state} dry heat/fire exposure" if state in dry_states else "Lower baseline fire exposure"),
        "sealevel": "Coastal sea-level and storm-surge exposure" if name in coastal else "Inland district; sea-level risk is minimal",
    }
    return risks, drivers, {k: {"events": v["events"], "prior": v["prior"]} for k, v in history.items()}


def _risk_from_weather(weather):
    c = weather.get("current", {})
    rain = float(c.get("precipitation") or 0)
    humidity = float(c.get("relative_humidity_2m") or 0)
    wind = float(c.get("wind_speed_10m") or 0)
    temp = float(c.get("temperature_2m") or 25)
    flood = min(1.0, 0.45 * min(rain / 25, 1) + 0.35 * min(humidity / 100, 1) + 0.20 * min(wind / 50, 1))
    fire = min(1.0, 0.55 * min(max(temp - 25, 0) / 20, 1) + 0.45 * (1 - min(humidity / 100, 1)))
    return {"flood": round(flood, 3), "earthquake": 0.0, "fire": round(fire, 3), "sealevel": 0.0}

def live_earthquakes(lat=20, lng=78, radius_km=1200):
    """USGS live earthquake feed; no key required."""
    key = _cache_key("earthquakes", round(lat, 3), round(lng, 3), int(radius_km))
    def fetch():
        r = requests.get("https://earthquake.usgs.gov/fdsnws/event/1/query", params={
            "format": "geojson", "latitude": lat, "longitude": lng,
            "maxradiuskm": radius_km, "minmagnitude": 2.5, "orderby": "time", "limit": 100
        }, timeout=_timeout())
        r.raise_for_status()
        out=[]
        for f in r.json().get("features", []):
            p=f.get("properties", {}); g=f.get("geometry", {}).get("coordinates", [None,None,None])
            out.append({"id":f.get("id"),"time":p.get("time"),"magnitude":p.get("mag"),
                        "place":p.get("place"),"lat":g[1],"lng":g[0],"depth_km":g[2],
                        "url":p.get("url")})
        return {"source":"USGS Earthquake Hazards Program","events":out}
    return _cached(key, fetch)

def live_fires(lat=20, lng=78, days=1, radius_deg=10):
    """NASA FIRMS live fire detections. Requires NASA_FIRMS_MAP_KEY."""
    key=os.getenv("NASA_FIRMS_MAP_KEY")
    if not key:
        return {"source":"NASA FIRMS","configured":False,"events":[],"message":"Set NASA_FIRMS_MAP_KEY in .env"}
    cache_key = _cache_key("fires", round(lat, 3), round(lng, 3), days, radius_deg)
    def fetch():
        # VIIRS NRT is used; API returns CSV.
        url=f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_SNPP_NRT/{lng-radius_deg},{lat-radius_deg},{lng+radius_deg},{lat+radius_deg}/{days}"
        r=requests.get(url,timeout=_timeout(8)); r.raise_for_status()
        import csv, io
        rows=list(csv.DictReader(io.StringIO(r.text)))
        events=[{"lat":float(x["latitude"]),"lng":float(x["longitude"]),
                 "brightness":float(x.get("bright_ti4") or x.get("brightness") or 0),
                 "confidence":x.get("confidence"),"acq_date":x.get("acq_date"),
                 "acq_time":x.get("acq_time"),"satellite":x.get("satellite")}
                for x in rows if x.get("latitude") and x.get("longitude")]
        return {"source":"NASA FIRMS VIIRS SNPP NRT","configured":True,"events":events}
    return _cached(cache_key, fetch)

def live_sealevel(lat, lng):
    """Stormglass marine API. Requires STORMGLASS_API_KEY."""
    key=os.getenv("STORMGLASS_API_KEY")
    if not key:
        return {"source":"Stormglass","configured":False,"data":[],"message":"Set STORMGLASS_API_KEY in .env"}
    cache_key = _cache_key("sealevel", round(lat, 3), round(lng, 3))
    def fetch():
        now=pd.Timestamp.utcnow()
        end=now+pd.Timedelta(hours=24)
        r=requests.get("https://api.stormglass.io/v2/weather/point",params={
            "lat":lat,"lng":lng,"params":"seaLevel,waveHeight,waterTemperature","start":now.isoformat(),"end":end.isoformat()
        },headers={"Authorization":key},timeout=_timeout(8))
        r.raise_for_status()
        return {"source":"Stormglass","configured":True,"data":r.json().get("hours",[])}
    return _cached(cache_key, fetch)

def hazard_snapshot(name):
    d=district(name)
    if not d: return None
    flood_score = d["risks"]["flood"]
    cache_key = _cache_key("hazard_snapshot", d["name"])
    def fetch():
        with ThreadPoolExecutor(max_workers=4) as pool:
            future_weather = pool.submit(_weather, d["name"])
            future_eq = pool.submit(live_earthquakes, d["lat"], d["lng"], 300)
            future_fires = pool.submit(live_fires, d["lat"], d["lng"], 1, 5)
            future_sea = pool.submit(live_sealevel, d["lat"], d["lng"])
            results = {}
            for label, future, fallback in [
                ("weather", future_weather, None),
                ("earthquakes", future_eq, {"events":[]}),
                ("fires", future_fires, {"events":[]}),
                ("sealevel", future_sea, {"data":[]}),
            ]:
                try:
                    results[label] = future.result()
                except Exception as exc:
                    results[label] = {**fallback, "error": str(exc)} if fallback is not None else None
        return results
    live = _cached(cache_key, fetch)
    if live.get("weather"):
        try:
            flood_score = _risk_from_weather(live["weather"])["flood"]
        except Exception:
            pass
    eq=live.get("earthquakes") or {"events":[]}
    fires=live.get("fires") or {"events":[]}
    sea=live.get("sealevel") or {"data":[]}
    eq_score=max([min(float(e.get("magnitude") or 0)/7,1) for e in eq["events"]] or [0])
    fire_score=max([min(float(e.get("brightness") or 0)/400,1) for e in fires["events"]] or [0])
    sea_vals=[]
    for h in sea.get("data",[]):
        v=h.get("seaLevel")
        if isinstance(v,dict): v=v.get("value")
        if isinstance(v,(int,float)): sea_vals.append(float(v))
    sea_score=min(1,max(0,(max(sea_vals)-min(sea_vals))/2)) if len(sea_vals)>1 else 0
    return {"district":d["name"],"coordinates":{"lat":d["lat"],"lng":d["lng"]},
            "flood":flood_score,"earthquake":round(eq_score,3),
            "fire":round(fire_score,3),"sealevel":round(sea_score,3),
            "earthquakes":eq["events"][:25],"fires":fires["events"][:100],"sealevel_data":sea.get("data",[]),
            "cached": live.get("cached", False)}

def _weather(name):
    cache_key = _cache_key("weather", name)
    def fetch():
        d = _geo(name)
        key = os.getenv("OPENWEATHER_API_KEY")
        if key:
            url = os.getenv("OPENWEATHER_BASE_URL", "https://api.openweathermap.org/data/2.5") + "/weather"
            r = requests.get(url, params={"lat": d["lat"], "lon": d["lng"], "appid": key, "units": "metric"}, timeout=_timeout())
            r.raise_for_status(); x = r.json()
            return {"source": "OpenWeather", "district": name, "coordinates": d, "current": {
                "temperature_2m": x.get("main", {}).get("temp"),
                "relative_humidity_2m": x.get("main", {}).get("humidity"),
                "precipitation": x.get("rain", {}).get("1h", 0),
                "wind_speed_10m": float(x.get("wind", {}).get("speed", 0)) * 3.6,
                "weather": (x.get("weather") or [{}])[0].get("description", "")
            }}
        r = requests.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": d["lat"], "longitude": d["lng"],
            "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
            "timezone": "Asia/Kolkata"
        }, timeout=_timeout())
        r.raise_for_status()
        return {"source": "Open-Meteo", "district": name, "coordinates": d,
                "current": r.json().get("current", {})}
    return _cached(cache_key, fetch)


def districts():
    out=[]
    for name,state in DISTRICT_SEEDS:
        lat,lng = DISTRICT_COORDS[name]
        risks, drivers, history = _baseline_risks(name,state,lat,lng)
        out.append({"name":name,"state":state,"lat":lat,"lng":lng,
                    "country":"India","risks":risks,
                    "risk_drivers":drivers,"historical_hazard_profile":history})
    return out

def district(name):
    for d in districts():
        if d["name"].lower() == name.lower():
            return d
    try:
        d = _geo(name); w = _weather(name)
        return {**d, "risks": _risk_from_weather(w)}
    except Exception:
        return None


def model():
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    # Blend simple generated "normal day" samples with the bundled historical
    # disaster CSV. This keeps the prototype lightweight while making district
    # patterns influence the model instead of relying only on synthetic rows.
    rng = np.random.default_rng(42)
    n = 2500
    rainfall = rng.gamma(2.2, 25, n)
    river = rng.uniform(0, 12, n)
    elevation = rng.uniform(0, 1200, n)
    temperature = rng.normal(29, 7, n)
    month = rng.integers(1, 13, n)
    score = (0.50 * np.clip(rainfall / 180, 0, 1) + 0.30 * np.clip(river / 10, 0, 1)
             + 0.12 * (1 - np.clip(elevation / 1000, 0, 1)) + 0.08 * np.sin((month - 1) / 12 * 2 * np.pi))
    y = (score + rng.normal(0, .08, n) > .48).astype(int)
    X = pd.DataFrame({"rainfall_mm": rainfall, "river_level_m": river, "elevation_m": elevation,
                      "temperature_c": temperature, "month": month})
    hist = historical_events()
    if not hist.empty:
        flood_like = hist["disaster_type"].str.lower().isin(["flood", "cyclone"])
        hist_X = pd.DataFrame({
            "rainfall_mm": hist["rainfall_mm"].astype(float).clip(0, 500),
            "river_level_m": np.where(flood_like, np.clip(hist["rainfall_mm"].astype(float) / 28, 1, 12), rng.uniform(0, 4, len(hist))),
            "elevation_m": np.where(hist["district"].isin(["Mumbai", "Chennai", "Kolkata", "Kochi", "Surat", "Bhubaneswar", "Patna", "Guwahati"]), rng.uniform(5, 90, len(hist)), rng.uniform(80, 900, len(hist))),
            "temperature_c": hist["temperature_c"].astype(float).clip(-5, 55),
            "month": hist["month"].astype(int),
        })
        hist_y = (flood_like & hist["severity"].isin(["MEDIUM", "HIGH", "CRITICAL"])).astype(int).to_numpy()
        # Add a few non-event comparison days around historical districts so the
        # model learns contrast, not only disaster examples.
        normal_n = max(300, len(hist) * 8)
        normal_X = pd.DataFrame({
            "rainfall_mm": rng.gamma(1.4, 12, normal_n),
            "river_level_m": rng.uniform(0, 4.5, normal_n),
            "elevation_m": rng.uniform(10, 900, normal_n),
            "temperature_c": rng.normal(30, 6, normal_n),
            "month": rng.integers(1, 13, normal_n),
        })
        X = pd.concat([X, hist_X, normal_X], ignore_index=True)
        y = np.concatenate([y, hist_y, np.zeros(normal_n, dtype=int)])
    rf = RandomForestClassifier(n_estimators=220, random_state=42, class_weight="balanced")
    gb = GradientBoostingClassifier(random_state=42)
    rf.fit(X, y); gb.fit(X, y)
    _MODEL = (rf, gb, list(X.columns))
    return _MODEL


def predict(payload):
    rf, gb, cols = model()
    district_name = payload.get("district") or "Delhi"
    live = bool(payload.get("use_live", False))
    features = {k: float(payload.get(k, 0)) for k in cols}
    if live:
        w = _weather(district_name)["current"]
        features.update({"rainfall_mm": float(w.get("precipitation") or 0),
                         "temperature_c": float(w.get("temperature_2m") or 25)})
        features["month"] = int(pd.Timestamp.now(tz="Asia/Kolkata").month)
    X = pd.DataFrame([features], columns=cols)
    model_probability = float((rf.predict_proba(X)[:, 1][0] + gb.predict_proba(X)[:, 1][0]) / 2)
    history = historical_profile(district_name)
    monsoon_boost = 0.06 if int(features.get("month", 1)) in [6, 7, 8, 9] else 0
    p = min(1.0, max(0.0, 0.78 * model_probability + 0.22 * history["flood_prior"] + monsoon_boost))
    level = "CRITICAL" if p >= .75 else "HIGH" if p >= .55 else "MEDIUM" if p >= .35 else "LOW"
    factor_rows = [
        {"factor": "rainfall_mm", "value": round(features["rainfall_mm"], 3), "note": "main flood trigger"},
        {"factor": "river_level_m", "value": round(features["river_level_m"], 3), "note": "river overflow pressure"},
        {"factor": "historical_flood_prior", "value": history["flood_prior"], "note": "based on bundled historical events"},
        {"factor": "month", "value": round(features["month"], 3), "note": "monsoon season adds risk" if monsoon_boost else "seasonal context"},
        {"factor": "elevation_m", "value": round(features["elevation_m"], 3), "note": "lower elevation increases exposure"},
    ]
    return {"district": district_name, "flood_probability": round(p, 4), "risk_level": level,
            "model_probability": round(model_probability, 4),
            "historical_context": history,
            "contributing_factors": factor_rows[:4],
            "features_used": cols, "live_data": live,
            "note": "Prototype estimate using weather inputs plus bundled historical event patterns; not an official warning."}


def _all_locations():
    return {d["name"]: d for d in districts()}


def _nearby_resources(points, limit=3):
    shelters, hospitals = _resource_rows()
    if not points:
        return {"shelters": [], "hospitals": []}
    route_districts = {p["name"].lower() for p in points}
    destination = points[-1]

    def rank(row):
        district_match = 0 if str(row.get("district", "")).lower() in route_districts else 1
        dist = _distance(destination, {"lat": float(row["latitude"]), "lng": float(row["longitude"])})
        return (district_match, dist)

    def shape(row):
        item = dict(row)
        item["distance_from_destination_km"] = round(_distance(destination, {"lat": float(row["latitude"]), "lng": float(row["longitude"])}), 1)
        return item

    return {
        "shelters": [shape(x) for x in sorted(shelters, key=rank)[:limit]],
        "hospitals": [shape(x) for x in sorted(hospitals, key=rank)[:limit]],
    }


def _format_road_instruction(step):
    maneuver = step.get("maneuver", {})
    road = step.get("name") or "local road"
    action = (maneuver.get("type") or "continue").replace("_", " ")
    modifier = maneuver.get("modifier") or ""
    distance_km = step.get("distance", 0) / 1000
    if action == "depart":
        text = f"Start on {road}"
    elif action == "arrive":
        text = "Arrive at safe destination"
    elif modifier:
        text = f"{action.title()} {modifier} onto {road}"
    else:
        text = f"{action.title()} on {road}"
    return {"instruction": text, "distance_km": round(distance_km, 2)}


def _road_route(points):
    if len(points) < 2:
        return {"geometry": [], "steps": [], "source": "none"}
    direct_distance = sum(_distance(points[i], points[i + 1]) for i in range(len(points) - 1))
    fallback = {
        "geometry": [{"lat": p["lat"], "lng": p["lng"]} for p in points],
        "steps": [{"instruction": f"Move from {points[0]['name']} toward {points[-1]['name']}", "distance_km": round(direct_distance, 2)}],
        "distance_km": round(direct_distance, 2),
        "duration_min": None,
        "source": "coordinate_estimate",
        "warning": "Road routing unavailable; showing direct coordinate estimate, not a verified road path.",
    }
    if "test" in sys.argv or os.getenv("DISABLE_ROAD_ROUTING", "False").lower() == "true":
        return fallback
    base = os.getenv("OSRM_ROUTE_URL", "https://router.project-osrm.org/route/v1/driving")
    coords = ";".join(f"{p['lng']},{p['lat']}" for p in points)
    try:
        res = requests.get(f"{base}/{coords}", params={"overview": "full", "geometries": "geojson", "steps": "true"}, timeout=min(_timeout(), 5))
        res.raise_for_status()
        data = res.json()
        routes = data.get("routes") or []
        if not routes:
            return fallback
        route_data = routes[0]
        geometry = [{"lat": lat, "lng": lng} for lng, lat in route_data.get("geometry", {}).get("coordinates", [])]
        steps = []
        for leg in route_data.get("legs", []):
            for step in leg.get("steps", []):
                item = _format_road_instruction(step)
                if item["distance_km"] >= 0.02 or not steps:
                    steps.append(item)
        return {
            "geometry": geometry or fallback["geometry"],
            "steps": steps[:8] or fallback["steps"],
            "distance_km": round(route_data.get("distance", 0) / 1000, 2),
            "duration_min": round(route_data.get("duration", 0) / 60, 1),
            "source": "osrm_road_route",
            "warning": "Road route from OSRM/OpenStreetMap. It does not know live flood water, blocked roads, police barricades, or bridge closures.",
        }
    except Exception:
        return fallback


def _local_safe_resources(origin_point, max_km=50):
    shelters, hospitals = _resource_rows()
    rows = []
    for kind, source in (("shelter", shelters), ("hospital", hospitals)):
        for row in source:
            if not row.get("latitude") or not row.get("longitude"):
                continue
            point = {"lat": float(row["latitude"]), "lng": float(row["longitude"])}
            dist = _distance(origin_point, point)
            same_district = str(row.get("district", "")).lower() == str(origin_point.get("name", "")).lower()
            if dist <= max_km or same_district:
                priority = 0 if kind == "shelter" else 1
                if same_district:
                    priority -= 1
                rows.append((priority, dist, kind, row))
    return sorted(rows, key=lambda x: (x[0], x[1]))


def _fallback_local_point(origin_point, hazard):
    # Approximate 20 km movement from the hazard center. It keeps demos local
    # when real shelter data is missing for a district.
    offsets = {
        "flood": (0.18, 0.0),       # move north / higher-ground estimate
        "fire": (-0.10, -0.16),     # move upwind/away estimate
        "earthquake": (0.08, 0.08), # open assembly estimate
        "sealevel": (0.18, 0.12),   # move inland/north-east estimate
    }
    dlat, dlng = offsets.get(hazard, (0.12, 0.12))
    direction = {
        "flood": "higher-ground local assembly point",
        "fire": "open upwind local assembly point",
        "earthquake": "open local assembly point",
        "sealevel": "inland higher-ground assembly point",
    }.get(hazard, "local safe assembly point")
    return {
        "name": f"Estimated {direction} near {origin_point['name']}",
        "district": origin_point["name"],
        "state": origin_point.get("state", "India"),
        "latitude": origin_point["lat"] + dlat,
        "longitude": origin_point["lng"] + dlng,
        "capacity": "Estimate",
        "contact": "112",
        "kind": "assembly_point",
        "description": "Estimated map point because no verified local shelter/hospital is available in bundled data.",
    }


def _local_evacuation_route(origin, hazard, ds, risk):
    origin_point = ds[origin]
    resources = _local_safe_resources(origin_point, max_km=50)
    if resources:
        _, distance, kind, row = resources[0]
        destination_name = row.get("name") or f"Nearest {kind.title()}"
        dest = {
            "name": destination_name,
            "state": row.get("state") or origin_point.get("state"),
            "lat": float(row["latitude"]),
            "lng": float(row["longitude"]),
        }
        destination_risk = max(0.05, risk[origin] - (0.25 if kind == "shelter" else 0.18))
        destination_detail = {"name": destination_name, "type": kind, "district": row.get("district", origin), "state": row.get("state", origin_point.get("state")), "distance_from_origin_km": round(distance, 1), "contact": row.get("contact", "112"), "capacity": row.get("capacity")}
        note = f"Local evacuation: nearest {kind} selected about {distance:.1f} km from {origin}. This is more practical than long-distance travel during an active hazard. Verify roads and follow official instructions."
        route_band = "local_resource"
        route_type = kind
    else:
        row = _fallback_local_point(origin_point, hazard)
        destination_name = row["name"]
        dest = {"name": destination_name, "state": row["state"], "lat": float(row["latitude"]), "lng": float(row["longitude"])}
        distance = _distance(origin_point, dest)
        destination_risk = max(0.08, risk[origin] - 0.16)
        destination_detail = {"name": destination_name, "type": "estimated assembly point", "district": row.get("district", origin), "state": row.get("state", origin_point.get("state")), "distance_from_origin_km": round(distance, 1), "contact": row.get("contact", "112"), "capacity": row.get("capacity"), "description": row.get("description", "Estimated local safe point")}
        note = f"Local evacuation estimate: no verified nearby shelter/hospital was found in bundled data, so the map shows an estimated local safe point about {distance:.1f} km from {origin}. Replace this with real ward-level shelter data for production use."
        route_band = "local_estimate"
        route_type = "assembly_point"

    points = [
        {"name": origin, "state": origin_point.get("state"), "lat": origin_point["lat"], "lng": origin_point["lng"],
         "risk_score": round(risk[origin], 3), "risk_level": "CRITICAL" if risk[origin]>=.75 else "HIGH" if risk[origin]>=.55 else "MEDIUM" if risk[origin]>=.35 else "LOW", "order": 0},
        {"name": destination_name, "state": dest.get("state"), "lat": dest["lat"], "lng": dest["lng"],
         "risk_score": round(destination_risk, 3), "risk_level": "CRITICAL" if destination_risk>=.75 else "HIGH" if destination_risk>=.55 else "MEDIUM" if destination_risk>=.35 else "LOW", "order": 1},
    ]
    road = _road_route(points)
    display_distance = road.get("distance_km") or round(distance, 1)
    return {"origin": origin, "destination": destination_name, "disaster_type": hazard,
            "total_path_risk": round(risk[origin] + destination_risk + display_distance / 100, 4),
            "num_waypoints": len(points), "waypoints": points,
            "origin_risk": round(risk[origin], 3), "destination_risk": round(destination_risk, 3),
            "route_mode": "local_resource", "route_band": route_band, "route_type": route_type,
            "destination_detail": destination_detail,
            "distance_km": round(display_distance, 2), "direct_distance_km": round(distance, 1),
            "duration_min": road.get("duration_min"), "route_source": road.get("source"),
            "route_geometry": road.get("geometry", []), "route_steps": road.get("steps", []),
            "route_warning": road.get("warning", ""),
            "suggested_resources": _nearby_resources(points),
            "route_note": note}


def route(origin, hazard="flood", destination=None):
    ds = _all_locations()
    if origin not in ds:
        return {"error": f"District '{origin}' not found"}
    if destination and destination not in ds:
        return {"error": f"District '{destination}' not found"}

    names = list(ds)
    risk = {n: ds[n]["risks"].get(hazard, .2) for n in names}
    if not destination:
        return _local_evacuation_route(origin, hazard, ds, risk)

    # Manual district routing is kept for demos/planned relocation. Default
    # hazard evacuation now stays local and uses shelters/resources first.
    g = {n: [] for n in names}
    for n in names:
        near = sorted((m for m in names if m != n), key=lambda m: _distance(ds[n], ds[m]))[:6]
        g[n] = near

    origin_risk = risk[origin]
    local_limit_km = 180
    regional_limit_km = 350
    max_auto_km = 500

    q = [(0, origin, [origin])]
    seen = set()
    best = {}
    while q:
        cost, node, path = heapq.heappop(q)
        if node in seen:
            continue
        seen.add(node)
        best[node] = (cost, path)
        if destination and node == destination:
            break
        for n in g[node]:
            if n not in seen:
                step_km = _distance(ds[node], ds[n])
                heapq.heappush(q, (cost + risk[n] + step_km / 900, n, path + [n]))

    if destination and destination not in best:
        return {"error": "No path found"}

    route_mode = "manual_destination" if destination else "nearby_auto"
    if not destination:
        candidates = []
        for n, (cost, path) in best.items():
            if n == origin:
                continue
            dist = _distance(ds[origin], ds[n])
            if dist > max_auto_km:
                continue
            safer_score = origin_risk - risk[n]
            if safer_score < 0.08 and risk[n] > 0.45:
                continue
            if dist <= local_limit_km:
                band = "local"
                band_penalty = 0
            elif dist <= regional_limit_km:
                band = "regional"
                band_penalty = 0.35
            else:
                band = "extended_nearby"
                band_penalty = 0.85
            practical_cost = risk[n] * 2.5 + dist / 250 + len(path) * 0.15 + band_penalty
            candidates.append((practical_cost, risk[n], dist, n, path, band))

        if not candidates:
            for n, (cost, path) in best.items():
                if n == origin:
                    continue
                dist = _distance(ds[origin], ds[n])
                if dist <= regional_limit_km:
                    candidates.append((risk[n] * 2.5 + dist / 250 + len(path) * 0.15, risk[n], dist, n, path, "nearest_available"))

        if not candidates:
            return {"error": "No practical nearby evacuation option found"}
        _, _, selected_distance, destination, path, band = min(candidates, key=lambda x: x[0])
    else:
        path = best[destination][1]
        selected_distance = _distance(ds[origin], ds[destination])
        band = "manual_far" if selected_distance > max_auto_km else "manual_nearby"

    points = [{"name": n, "state": ds[n].get("state"), "lat": ds[n]["lat"], "lng": ds[n]["lng"],
               "risk_score": round(risk[n], 3), "risk_level": "CRITICAL" if risk[n]>=.75 else "HIGH" if risk[n]>=.55 else "MEDIUM" if risk[n]>=.35 else "LOW", "order": i}
              for i, n in enumerate(path)]
    resources = _nearby_resources(points)
    if route_mode == "nearby_auto":
        note = f"Practical nearby evacuation: selected {destination} because it is safer and about {selected_distance:.0f} km from {origin}. Prefer listed shelters first and follow official instructions."
    elif band == "manual_far":
        note = f"Manual long-distance route: {destination} is about {selected_distance:.0f} km from {origin}. In real hazards, use this only for planned relocation; prefer nearby shelters or safer districts first."
    else:
        note = f"Manual nearby route: {destination} is about {selected_distance:.0f} km from {origin}. Verify roads, shelters, and official instructions before movement."
    road = _road_route(points)
    display_distance = road.get("distance_km") or round(selected_distance, 1)
    return {"origin": origin, "destination": destination, "disaster_type": hazard,
            "total_path_risk": round(best[destination][0], 4), "num_waypoints": len(points),
            "waypoints": points, "origin_risk": round(origin_risk, 3), "destination_risk": round(risk[destination], 3),
            "route_mode": route_mode, "route_band": band,
            "destination_detail": {"name": destination, "type": "district", "district": destination, "state": ds[destination].get("state"), "distance_from_origin_km": round(selected_distance, 1), "contact": "112"},
            "distance_km": round(display_distance, 2),
            "direct_distance_km": round(selected_distance, 1), "duration_min": road.get("duration_min"),
            "route_source": road.get("source"), "route_geometry": road.get("geometry", []),
            "route_steps": road.get("steps", []), "route_warning": road.get("warning", ""),
            "suggested_resources": resources,
            "route_note": note}


def _distance(a, b):
    r = 6371.0
    p1, p2 = math.radians(a["lat"]), math.radians(b["lat"])
    dp = math.radians(b["lat"] - a["lat"]); dl = math.radians(b["lng"] - a["lng"])
    h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*r*math.asin(math.sqrt(h))


def live_weather(name):
    return _weather(name)


def news_alerts():
    key = os.getenv("NEWSAPI_KEY")
    if not key: return []
    def fetch():
        url = os.getenv("NEWSAPI_BASE_URL", "https://newsapi.org/v2") + "/everything"
        r = requests.get(url, params={"q": "India flood OR cyclone OR earthquake OR wildfire",
                                      "language": "en", "sortBy": "publishedAt", "pageSize": 20, "apiKey": key}, timeout=_timeout())
        r.raise_for_status()
        return [{"level": "INFO", "district": "India", "hazard": "multi", "message": a.get("title", ""), "source": a.get("url", "")}
                for a in r.json().get("articles", [])]
    return _cached(_cache_key("news_alerts", "india"), fetch)


HAZARD_SEASONALITY = {
    "flood": {"peak_month": 8, "amplitude": 0.14, "label": "Flood"},
    "earthquake": {"peak_month": 1, "amplitude": 0.03, "label": "Earthquake"},
    "fire": {"peak_month": 5, "amplitude": 0.12, "label": "Fire"},
    "sealevel": {"peak_month": 10, "amplitude": 0.08, "label": "Sea Level"},
}


def _seasonal_value(base, month, peak_month, amplitude):
    seasonal = math.cos((month - peak_month) / 12 * 2 * math.pi)
    return round(min(1, max(0, base + seasonal * amplitude)), 3)


def monthly(name, hazard="flood"):
    d = district(name)
    if not d: return {"error": "District not found"}
    hazard = hazard if hazard in HAZARD_SEASONALITY else "flood"
    monthly_risks = []
    for m in range(1, 13):
        row = {"month": m}
        for key, cfg in HAZARD_SEASONALITY.items():
            row[key] = _seasonal_value(d["risks"].get(key, 0), m, cfg["peak_month"], cfg["amplitude"])
        monthly_risks.append(row)
    peak = max(monthly_risks, key=lambda x: x[hazard])
    return {
        "district": d["name"],
        "hazard": hazard,
        "hazard_label": HAZARD_SEASONALITY[hazard]["label"],
        "monthly_risks": monthly_risks,
        "series": [{"month": x["month"], "risk": x[hazard]} for x in monthly_risks],
        "peak_month": peak["month"],
        "peak_value": peak[hazard],
        "available_hazards": [{"id": k, "label": v["label"]} for k, v in HAZARD_SEASONALITY.items()],
    }
