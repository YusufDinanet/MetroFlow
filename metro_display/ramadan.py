"""Ramadan prayer-time footer (Istanbul)."""
import json
import re
import ssl
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

try:
    import certifi  # type: ignore
except Exception:  # noqa: BLE001
    certifi = None

from . import config

if certifi:
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
else:
    SSL_CONTEXT = None

_DAILY_CACHE: Dict[str, Optional["PrayerTimes"]] = {}
# Offline safety net for the requested demo day.
_FALLBACK_TIMES = {
    ("istanbul", "turkey", 13): {
        "2026-02-20": ("06:10", "18:51"),
    }
}


@dataclass(frozen=True)
class PrayerTimes:
    day: date
    imsak: str
    iftar: str


def _urlopen(req, timeout: int):
    if SSL_CONTEXT is not None:
        return urllib.request.urlopen(req, timeout=timeout, context=SSL_CONTEXT)
    return urllib.request.urlopen(req, timeout=timeout)


def _parse_iso_date(raw: str) -> Optional[date]:
    if not raw:
        return None
    try:
        parts = raw.strip().split("-")
        if len(parts) != 3:
            return None
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None


def _extract_hhmm(raw: str) -> str:
    if not raw:
        return ""
    match = re.search(r"(\d{1,2}):(\d{2})", raw)
    if not match:
        return ""
    hour = int(match.group(1))
    minute = int(match.group(2))
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return ""
    return f"{hour:02d}:{minute:02d}"


def _build_url(day: date) -> str:
    day_key = day.strftime("%d-%m-%Y")
    params = urllib.parse.urlencode(
        {
            "city": config.RAMADAN_CITY,
            "country": config.RAMADAN_COUNTRY,
            "method": str(config.RAMADAN_METHOD),
        }
    )
    return f"{config.RAMADAN_API_BASE_URL}/{day_key}?{params}"


def _fetch_day_times(day: date) -> Optional[PrayerTimes]:
    cache_key = day.isoformat()
    if cache_key in _DAILY_CACHE:
        return _DAILY_CACHE[cache_key]

    req = urllib.request.Request(_build_url(day), headers={"Accept": "application/json"}, method="GET")
    try:
        with _urlopen(req, timeout=config.RAMADAN_TIMEOUT_SECONDS) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:  # noqa: BLE001
        fallback = _fallback_day_times(day)
        _DAILY_CACHE[cache_key] = fallback
        return fallback

    data = payload.get("data") or {}
    timings = data.get("timings") or {}
    imsak = _extract_hhmm(timings.get("Imsak") or timings.get("Fajr") or "")
    iftar = _extract_hhmm(timings.get("Maghrib") or timings.get("Sunset") or "")
    if not imsak or not iftar:
        fallback = _fallback_day_times(day)
        _DAILY_CACHE[cache_key] = fallback
        return fallback

    gregorian = (data.get("date") or {}).get("gregorian") or {}
    date_key = gregorian.get("date") or ""
    day_obj = day
    if date_key:
        try:
            dd, mm, yyyy = date_key.split("-")
            day_obj = date(int(yyyy), int(mm), int(dd))
        except ValueError:
            day_obj = day

    result = PrayerTimes(day=day_obj, imsak=imsak, iftar=iftar)
    _DAILY_CACHE[cache_key] = result
    return result


def _fallback_day_times(day: date) -> Optional[PrayerTimes]:
    key = (
        config.RAMADAN_CITY.strip().lower(),
        config.RAMADAN_COUNTRY.strip().lower(),
        int(config.RAMADAN_METHOD),
    )
    day_map = _FALLBACK_TIMES.get(key) or {}
    pair = day_map.get(day.isoformat())
    if not pair:
        return None
    return PrayerTimes(day=day, imsak=pair[0], iftar=pair[1])


def _target_date(now: datetime) -> Tuple[date, bool]:
    forced = _parse_iso_date(config.RAMADAN_TARGET_DATE)
    if forced:
        return forced, True
    return now.date(), False


def _minutes_until(now: datetime, target_day: date, hhmm: str) -> Optional[int]:
    hh, mm = hhmm.split(":")
    target = now.replace(
        year=target_day.year,
        month=target_day.month,
        day=target_day.day,
        hour=int(hh),
        minute=int(mm),
        second=0,
        microsecond=0,
    )
    delta = int((target - now).total_seconds())
    if delta <= 0:
        return None
    return (delta + 59) // 60


def _format_remaining(minutes: Optional[int]) -> str:
    if minutes is None:
        return "gecti"
    hours = minutes // 60
    mins = minutes % 60
    if hours > 0:
        return f"{hours}s {mins:02d}d"
    return f"{mins}d"


def _resolve_remaining_for_dynamic_day(now: datetime, key: str, today: PrayerTimes) -> Tuple[str, Optional[int]]:
    current_time = today.imsak if key == "imsak" else today.iftar
    remaining = _minutes_until(now, today.day, current_time)
    if remaining is not None:
        return current_time, remaining

    tomorrow = _fetch_day_times(today.day + timedelta(days=1))
    if tomorrow is None:
        return current_time, None
    tomorrow_time = tomorrow.imsak if key == "imsak" else tomorrow.iftar
    return tomorrow_time, _minutes_until(now, tomorrow.day, tomorrow_time)


def get_ramadan_footer_lines(now: datetime) -> List[str]:
    if not config.SHOW_RAMADAN_PANEL:
        return []

    day, is_fixed_day = _target_date(now)
    today = _fetch_day_times(day)
    if today is None:
        return ["Ramazan: veri alinamadi"]

    if is_fixed_day:
        imsak_time = today.imsak
        iftar_time = today.iftar
        imsak_left = _minutes_until(now, today.day, imsak_time)
        iftar_left = _minutes_until(now, today.day, iftar_time)
    else:
        imsak_time, imsak_left = _resolve_remaining_for_dynamic_day(now, "imsak", today)
        iftar_time, iftar_left = _resolve_remaining_for_dynamic_day(now, "iftar", today)

    date_label = today.day.strftime("%d.%m.%Y")
    line1 = f"Ramazan {date_label} - {config.RAMADAN_CITY}"
    line2 = (
        f"Imsak {imsak_time} ({_format_remaining(imsak_left)}) | "
        f"Iftar {iftar_time} ({_format_remaining(iftar_left)})"
    )
    return [line1, line2]
