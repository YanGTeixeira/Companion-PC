"""Clima (Open-Meteo, sem conta) e agenda (endereço secreto iCal do Google Agenda).

O link iCal fica só no config.json do PC; o celular recebe apenas os compromissos de hoje e amanhã.
Recorrências (reunião toda segunda etc.) precisam dos pacotes icalendar e recurring_ical_events;
sem eles, só os compromissos avulsos aparecem.
"""
import datetime as dt
import json
import logging
import re
import urllib.parse
import urllib.request

log = logging.getLogger("companion")

UA = {"User-Agent": "CompanionPC/1.9"}
MEET_RE = re.compile(r"https://meet\.google\.com/[a-z]{3}-[a-z]{4}-[a-z]{3}")

WMO = {0: "Céu limpo", 1: "Quase limpo", 2: "Parcialmente nublado", 3: "Nublado", 45: "Neblina", 48: "Neblina",
       51: "Garoa fraca", 53: "Garoa", 55: "Garoa forte", 56: "Garoa gelada", 57: "Garoa gelada",
       61: "Chuva fraca", 63: "Chuva", 65: "Chuva forte", 66: "Chuva gelada", 67: "Chuva gelada",
       71: "Neve fraca", 73: "Neve", 75: "Neve forte", 77: "Neve", 80: "Pancadas fracas", 81: "Pancadas de chuva",
       82: "Pancadas fortes", 85: "Neve", 86: "Neve", 95: "Trovoadas", 96: "Trovoadas com granizo", 99: "Trovoadas com granizo"}


def _get(url, timeout=12):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


# --------------------------------------------------------------------------
# Clima
# --------------------------------------------------------------------------
_geo_cache = {}


def geocode(city):
    if city in _geo_cache:
        return _geo_cache[city]
    q = urllib.parse.urlencode({"name": city.split(",")[0].strip(), "count": 5, "language": "pt", "format": "json"})
    res = json.loads(_get("https://geocoding-api.open-meteo.com/v1/search?" + q)).get("results") or []
    if not res:
        raise ValueError(f"cidade não encontrada: {city}")
    # "Cidade, UF" ou "Cidade, País": prefere o resultado que bate com o que vem depois da vírgula
    extra = city.split(",")[1].strip().lower() if "," in city else ""
    best = next((r for r in res if extra and extra in " ".join(str(r.get(k, "")) for k in ("admin1", "country", "country_code")).lower()), res[0])
    g = {"name": best["name"], "region": best.get("admin1") or best.get("country") or "", "lat": best["latitude"], "lon": best["longitude"]}
    _geo_cache[city] = g
    return g


def weather(city):
    """Open-Meteo; se estiver fora do ar ou sobrecarregado, wttr.in."""
    g = geocode(city)
    try:
        return _open_meteo(g)
    except Exception as e:  # noqa: BLE001
        log.info("clima: Open-Meteo falhou (%s), usando wttr.in", e)
        try:
            return _wttr(g)
        except Exception as e2:  # noqa: BLE001
            raise RuntimeError(f"Open-Meteo: {e}; wttr.in: {e2}") from e2


def _wttr(g):
    d = json.loads(_get(f"https://wttr.in/{g['lat']:.4f},{g['lon']:.4f}?format=j1&lang=pt", timeout=20))
    c, days = d["current_condition"][0], d["weather"]
    pt = lambda x: ((x.get("lang_pt") or x.get("weatherDesc") or [{}])[0].get("value") or "").strip()  # noqa: E731
    now_h = dt.datetime.now().hour
    hrs = []
    for di, day in enumerate(days[:2]):
        for h in day["hourly"]:
            hh = int(h["time"]) // 100
            if di == 1 or hh >= now_h - 1:
                hrs.append({"h": f"{hh:02d}", "t": int(h["tempC"]), "p": int(h["chanceofrain"])})
    hrs = hrs[:6]
    rain = None
    for di, day in enumerate(days[:2]):
        for h in day["hourly"]:
            hh = int(h["time"]) // 100
            if (di == 1 or hh >= now_h) and int(h["chanceofrain"]) >= 50:
                rain = {"at": ("amanhã " if di else "") + f"{hh:02d}:00", "pct": int(h["chanceofrain"])}
                break
        if rain:
            break
    mx = lambda day: max(int(h["chanceofrain"]) for h in day["hourly"])  # noqa: E731
    t0, t1 = days[0], days[1] if len(days) > 1 else None
    return {"city": g["name"], "region": g["region"], "temp": int(c["temp_C"]), "feels": int(c["FeelsLikeC"]),
            "code": None, "desc": pt(c), "day": True, "max": int(t0["maxtempC"]), "min": int(t0["mintempC"]),
            "rain_pct": mx(t0), "rain": rain, "hours": hrs, "src": "wttr.in",
            "tomorrow": {"max": int(t1["maxtempC"]), "min": int(t1["mintempC"]), "rain_pct": mx(t1),
                         "desc": pt(t1["hourly"][4])} if t1 else None}


def _open_meteo(g):
    q = urllib.parse.urlencode({
        "latitude": g["lat"], "longitude": g["lon"], "timezone": "auto", "forecast_days": 2,
        "current": "temperature_2m,apparent_temperature,weather_code,is_day",
        "hourly": "precipitation_probability,temperature_2m,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code"})
    d = json.loads(_get("https://api.open-meteo.com/v1/forecast?" + q, timeout=10))
    cur, daily, hourly = d.get("current") or {}, d.get("daily") or {}, d.get("hourly") or {}
    now = cur.get("time", "")[:13]
    times = hourly.get("time") or []
    start = next((i for i, t in enumerate(times) if t[:13] >= now), 0)
    rain = None
    for i in range(start, min(start + 12, len(times))):
        if (hourly["precipitation_probability"][i] or 0) >= 50:
            rain = {"at": ("amanhã " if times[i][:10] > now[:10] else "") + times[i][11:16], "pct": hourly["precipitation_probability"][i]}
            break
    hours = [{"h": times[i][11:13], "t": round(hourly["temperature_2m"][i]), "p": hourly["precipitation_probability"][i]}
             for i in range(start, min(start + 12, len(times)), 2)]
    code = cur.get("weather_code")
    return {"city": g["name"], "region": g["region"], "temp": round(cur.get("temperature_2m", 0)),
            "feels": round(cur.get("apparent_temperature", 0)), "code": code, "desc": WMO.get(code, ""),
            "day": bool(cur.get("is_day", 1)),
            "max": round(daily["temperature_2m_max"][0]), "min": round(daily["temperature_2m_min"][0]),
            "rain_pct": daily["precipitation_probability_max"][0], "rain": rain, "hours": hours,
            "tomorrow": {"max": round(daily["temperature_2m_max"][1]), "min": round(daily["temperature_2m_min"][1]),
                         "rain_pct": daily["precipitation_probability_max"][1],
                         "desc": WMO.get(daily["weather_code"][1], "")} if len(daily.get("time") or []) > 1 else None}


# --------------------------------------------------------------------------
# Agenda
# --------------------------------------------------------------------------
def _local(v):
    """date ou datetime (com ou sem fuso) -> datetime local sem fuso; date -> (datetime 00:00, dia inteiro)."""
    if isinstance(v, dt.datetime):
        return (v.astimezone().replace(tzinfo=None) if v.tzinfo else v), False
    return dt.datetime.combine(v, dt.time()), True


def _event(ev):
    start, all_day = _local(ev.get("DTSTART").dt)
    end_p = ev.get("DTEND")
    end = _local(end_p.dt)[0] if end_p else start + (dt.timedelta(days=1) if all_day else dt.timedelta(hours=1))
    text = " ".join(str(ev.get(k, "")) for k in ("X-GOOGLE-CONFERENCE", "LOCATION", "DESCRIPTION"))
    m = MEET_RE.search(text)
    return {"title": str(ev.get("SUMMARY", "")).strip() or "(sem título)", "start": start.isoformat(timespec="minutes"),
            "end": end.isoformat(timespec="minutes"), "all_day": all_day, "link": m.group(0) if m else None,
            "where": str(ev.get("LOCATION", "")).strip()[:80] if not m else ""}


def calendar(url):
    if not url.startswith(("https://", "webcal://")):
        raise ValueError("o link da agenda tem que começar com https://")
    raw = _get(url.replace("webcal://", "https://", 1), timeout=20)
    from icalendar import Calendar
    cal = Calendar.from_ical(raw)
    today = dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    until = today + dt.timedelta(days=2)
    try:
        import recurring_ical_events
        items = recurring_ical_events.of(cal).between(today, until)
    except ImportError:
        items = [c for c in cal.walk("VEVENT") if not c.get("RRULE")]
    out = []
    for ev in items:
        try:
            e = _event(ev)
        except Exception:  # noqa: BLE001  (evento estranho: pula)
            continue
        if str(ev.get("STATUS", "")).upper() == "CANCELLED":
            continue
        if e["end"] > today.isoformat() and e["start"] < until.isoformat():
            out.append(e)
    out.sort(key=lambda e: (e["start"], e["title"]))
    return out[:30]
