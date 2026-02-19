"""Live timetable providers for M4 and Marmaray."""
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from html import unescape
from typing import Dict, List, Optional, Tuple

try:
    import certifi  # type: ignore
except Exception:  # noqa: BLE001
    certifi = None

from . import config
from .gtfs.parser import normalize_text
from .schedule.next_trips import Departure

if certifi:
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
else:
    SSL_CONTEXT = None

_M4_META_CACHE = {"expires_at": 0.0, "station_norm": "", "value": None}
_TCDD_TOKEN = config.MARMARAY_API_BASIC_TOKEN
_EURO_KEYS = [normalize_text(k) for k in config.MARMARAY_EUROPE_KEYWORDS]
_ANATOLIA_KEYS = [normalize_text(k) for k in config.MARMARAY_ANATOLIA_KEYWORDS]


def _urlopen(req, timeout: int):
    if SSL_CONTEXT is not None:
        return urllib.request.urlopen(req, timeout=timeout, context=SSL_CONTEXT)
    return urllib.request.urlopen(req, timeout=timeout)


def _http_get_text(url: str, headers: Optional[Dict[str, str]] = None, timeout: Optional[int] = None) -> str:
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    with _urlopen(req, timeout=timeout or config.LIVE_TIMEOUT_SECONDS) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _http_get_json(url: str, headers: Optional[Dict[str, str]] = None, timeout: Optional[int] = None):
    raw = _http_get_text(url, headers=headers, timeout=timeout)
    return json.loads(raw)


def _encode_multipart(fields: Dict[str, str]) -> Tuple[str, bytes]:
    boundary = "----metrodisplay" + uuid.uuid4().hex
    lines = []
    for key, value in fields.items():
        lines.append(f"--{boundary}\r\n")
        lines.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n')
        lines.append(f"{value}\r\n")
    lines.append(f"--{boundary}--\r\n")
    body = "".join(lines).encode("utf-8")
    return boundary, body


def _http_post_multipart_json(
    url: str,
    fields: Dict[str, str],
    headers: Optional[Dict[str, str]] = None,
    timeout: Optional[int] = None,
):
    boundary, body = _encode_multipart(fields)
    req_headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body)),
    }
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=body, headers=req_headers, method="POST")
    with _urlopen(req, timeout=timeout or config.LIVE_TIMEOUT_SECONDS) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def _strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _extract_select_options(html: str, select_id: str) -> List[Tuple[str, str]]:
    pattern = rf"<select[^>]*id=['\"]{re.escape(select_id)}['\"][^>]*>(.*?)</select>"
    match = re.search(pattern, html, re.S | re.I)
    if not match:
        return []
    select_body = match.group(1)
    options = []
    for value, label in re.findall(r"<option[^>]*value=['\"]([^'\"]*)['\"][^>]*>(.*?)</option>", select_body, re.S | re.I):
        options.append((value.strip(), _strip_tags(unescape(label))))
    return options


def _extract_m4_meta(station_name: str) -> Dict[str, str]:
    html = _http_get_text(config.M4_TIMETABLE_PAGE_URL, timeout=config.LIVE_TIMEOUT_SECONDS)
    route_options = _extract_select_options(html, "seferler_3")
    station_options = _extract_select_options(html, "istasyonlar_3")

    route_to_sabiha = ""
    route_to_kadikoy = ""
    for route_id, label in route_options:
        norm = normalize_text(label)
        if not route_id:
            continue
        if norm.startswith("kadikoy") and "sabihagokcenhavalimani" in norm:
            route_to_sabiha = route_id
        elif norm.startswith("sabihagokcenhavalimani") and "kadikoy" in norm:
            route_to_kadikoy = route_id

    if not route_to_sabiha and route_options:
        route_to_sabiha = route_options[0][0]
    if not route_to_kadikoy and len(route_options) > 1:
        route_to_kadikoy = route_options[1][0]

    station_norm = normalize_text(station_name)
    station_id = ""
    for value, label in station_options:
        if not value:
            continue
        norm = normalize_text(label)
        if norm == station_norm:
            station_id = value
            break
    if not station_id:
        for value, label in station_options:
            if not value:
                continue
            norm = normalize_text(label)
            if station_norm in norm or norm in station_norm:
                station_id = value
                break

    kod_match = re.search(r'formData\.append\(\s*"kod"\s*,\s*[\'"]([^\'"]+)[\'"]\s*\)', html)
    kod = kod_match.group(1) if kod_match else ""

    if not route_to_sabiha or not route_to_kadikoy or not station_id or not kod:
        raise RuntimeError("Could not parse M4 timetable metadata from Metro Istanbul page")

    return {
        "route_to_sabiha": route_to_sabiha,
        "route_to_kadikoy": route_to_kadikoy,
        "station_id": station_id,
        "kod": kod,
    }


def _get_m4_meta(station_name: str) -> Dict[str, str]:
    now_ts = time.time()
    station_norm = normalize_text(station_name)
    cached = _M4_META_CACHE.get("value")
    if cached and now_ts < _M4_META_CACHE.get("expires_at", 0) and _M4_META_CACHE.get("station_norm") == station_norm:
        return cached

    meta = _extract_m4_meta(station_name)
    _M4_META_CACHE["value"] = meta
    _M4_META_CACHE["station_norm"] = station_norm
    _M4_META_CACHE["expires_at"] = now_ts + config.LIVE_META_CACHE_SECONDS
    return meta


def _minutes_until(now, hhmm: str) -> Optional[int]:
    if not hhmm or len(hhmm) < 5:
        return None
    try:
        hh = int(hhmm[0:2])
        mm = int(hhmm[3:5])
    except ValueError:
        return None
    if hh < 0 or hh > 23 or mm < 0 or mm > 59:
        return None

    now_minutes = now.hour * 60 + now.minute
    target_minutes = hh * 60 + mm
    delta = target_minutes - now_minutes
    if delta < -config.LIVE_DAY_WRAP_THRESHOLD_MINUTES:
        delta += 24 * 60
    if delta < 0:
        return None
    return delta


def _sort_and_dedupe(departures: List[Departure], limit: int) -> List[Departure]:
    departures.sort(key=lambda d: d.minutes)
    out = []
    seen = set()
    for dep in departures:
        if dep.time_str in seen:
            continue
        seen.add(dep.time_str)
        out.append(dep)
        if len(out) >= limit:
            break
    return out


def _m4_direction_departures(now, payload: dict, limit: int) -> List[Departure]:
    rows = payload.get("sefer") or []
    out = []
    for row in rows:
        hhmm = (row.get("zaman") or "").strip()
        delta = _minutes_until(now, hhmm)
        if delta is None:
            continue
        out.append(Departure(minutes=delta, time_str=hhmm))
    return _sort_and_dedupe(out, limit)


def fetch_m4_departures(now, station_name: str, limit: int) -> Dict[str, List[Departure]]:
    """Returns keys: kadikoy, sabiha."""
    meta = _get_m4_meta(station_name)
    common_fields = {
        "secim": "1",
        "saat": "",
        "dakika": "",
        "tarih1": "",
        "tarih2": "",
        "station": meta["station_id"],
        "kod": meta["kod"],
    }

    out: Dict[str, List[Departure]] = {}
    route_map = {
        "sabiha": meta["route_to_sabiha"],
        "kadikoy": meta["route_to_kadikoy"],
    }
    for key, route_id in route_map.items():
        fields = dict(common_fields)
        fields["route"] = route_id
        try:
            payload = _http_post_multipart_json(
                config.M4_TIMETABLE_AJAX_URL,
                fields,
                headers={"Accept": "application/json"},
            )
            out[key] = _m4_direction_departures(now, payload, limit)
        except Exception:  # noqa: BLE001
            out[key] = []
    return out


def _tcdd_headers(token: str) -> Dict[str, str]:
    return {
        "Accept": "application/json",
        "Authorization": f"Basic {token}",
        "User-Agent": "metro-display/1.0",
    }


def _extract_tcdd_token() -> Optional[str]:
    page_html = _http_get_text(config.MARMARAY_TIMETABLE_PAGE_URL, timeout=config.LIVE_TIMEOUT_SECONDS)
    script_match = re.search(r"<script[^>]*src=['\"]([^'\"]*main\.[^'\"]+\.js)['\"]", page_html, re.I)
    if not script_match:
        return None
    script_url = urllib.parse.urljoin(config.MARMARAY_TIMETABLE_PAGE_URL, script_match.group(1))
    script_body = _http_get_text(script_url, timeout=max(config.LIVE_TIMEOUT_SECONDS, 30))
    token_match = re.search(r'getAuthToken\(\)\{return"([^"]+)"\}', script_body)
    if not token_match:
        return None
    return token_match.group(1)


def _fetch_marmaray_rows() -> List[dict]:
    global _TCDD_TOKEN

    try:
        data = _http_get_json(config.MARMARAY_API_URL, headers=_tcdd_headers(_TCDD_TOKEN), timeout=config.LIVE_TIMEOUT_SECONDS)
        if isinstance(data, list):
            return data
    except urllib.error.HTTPError as err:
        if err.code != 401:
            raise

    fresh_token = _extract_tcdd_token()
    if fresh_token:
        _TCDD_TOKEN = fresh_token
        data = _http_get_json(config.MARMARAY_API_URL, headers=_tcdd_headers(_TCDD_TOKEN), timeout=config.LIVE_TIMEOUT_SECONDS)
        if isinstance(data, list):
            return data
    return []


def _contains_any(text_norm: str, keywords: List[str]) -> bool:
    return any(k in text_norm for k in keywords)


def _classify_marmaray_direction(origin: str, destination: str) -> str:
    dest = normalize_text(destination or "")
    orig = normalize_text(origin or "")

    dest_euro = _contains_any(dest, _EURO_KEYS)
    dest_ana = _contains_any(dest, _ANATOLIA_KEYS)
    if dest_euro and not dest_ana:
        return "avrupa"
    if dest_ana and not dest_euro:
        return "anadolu"

    orig_euro = _contains_any(orig, _EURO_KEYS)
    orig_ana = _contains_any(orig, _ANATOLIA_KEYS)
    if orig_ana and not orig_euro:
        return "avrupa"
    if orig_euro and not orig_ana:
        return "anadolu"
    return ""


def _pick_station_time(hour_row: dict) -> str:
    for key in ("originTime", "destinationTime"):
        value = (hour_row.get(key) or "").strip()
        if value and value != "00:00:00":
            return value[0:5]
    return ""


def fetch_marmaray_departures(now, station_name: str, limit: int) -> Dict[str, List[Departure]]:
    """Returns keys: avrupa, anadolu."""
    rows = _fetch_marmaray_rows()
    station_norm = normalize_text(station_name)

    out = {"avrupa": [], "anadolu": []}
    for row in rows:
        train_code = str(row.get("trainCode") or "")
        if config.MARMARAY_TRAIN_CODE_PREFIX and not train_code.startswith(config.MARMARAY_TRAIN_CODE_PREFIX):
            continue

        direction = _classify_marmaray_direction(row.get("originStation") or "", row.get("destinationStation") or "")
        if direction not in out:
            continue

        for hour_row in row.get("hours") or []:
            hour_station = normalize_text(hour_row.get("station") or "")
            if hour_station != station_norm:
                continue
            hhmm = _pick_station_time(hour_row)
            delta = _minutes_until(now, hhmm)
            if delta is None:
                continue
            out[direction].append(Departure(minutes=delta, time_str=hhmm))

    out["avrupa"] = _sort_and_dedupe(out["avrupa"], limit)
    out["anadolu"] = _sort_and_dedupe(out["anadolu"], limit)
    return out


def fetch_live_line_departures(line_name: str, station_name: str, now, limit: int) -> Dict[str, List[Departure]]:
    """Returns direction-keyed live departures (keys are normalized labels)."""
    line_norm = normalize_text(line_name)
    if line_norm == "m4":
        return fetch_m4_departures(now, station_name, limit)
    if "marmaray" in line_norm:
        return fetch_marmaray_departures(now, station_name, limit)
    return {}
