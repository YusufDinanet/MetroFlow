"""Compute next departures based on GTFS schedule."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Set, Tuple

try:  # Python 3.9+
    from zoneinfo import ZoneInfo  # type: ignore
except Exception:  # noqa: BLE001
    ZoneInfo = None

from .. import config
from ..db import query
from ..gtfs.parser import normalize_text, seconds_to_hhmm


@dataclass
class Departure:
    minutes: int
    time_str: str
    is_next_day: bool = False


def _active_service_ids(conn, date_key: str, weekday: int) -> Set[str]:
    cols = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    col = cols[weekday]
    rows = query(
        conn,
        f"""
        SELECT service_id FROM calendar
        WHERE start_date <= ? AND end_date >= ? AND {col} = 1
        """,
        (date_key, date_key),
    )
    active = {r["service_id"] for r in rows}

    ex_rows = query(
        conn,
        "SELECT service_id, exception_type FROM calendar_dates WHERE date = ?",
        (date_key,),
    )
    for r in ex_rows:
        if r["exception_type"] == 1:
            active.add(r["service_id"])
        elif r["exception_type"] == 2:
            active.discard(r["service_id"])
    return active


def _date_key(d: datetime) -> str:
    return d.strftime("%Y%m%d")


def _calendar_range(conn) -> Tuple[Optional[str], Optional[str]]:
    rows = query(conn, "SELECT MIN(start_date) AS min_start, MAX(end_date) AS max_end FROM calendar")
    if not rows:
        return None, None
    return rows[0]["min_start"], rows[0]["max_end"]


def _parse_date_key(key: str) -> Optional[datetime]:
    if not key or len(key) != 8:
        return None
    try:
        return datetime(int(key[0:4]), int(key[4:6]), int(key[6:8]))
    except ValueError:
        return None


def _find_nearest_in_range(now: datetime, min_key: str, max_key: str) -> Optional[Tuple[datetime, str]]:
    target_dow = now.weekday()
    if now.strftime("%Y%m%d") > max_key:
        date = _parse_date_key(max_key)
        if not date:
            return None
        for _ in range(7):
            if date.weekday() == target_dow:
                return date, _date_key(date)
            date -= timedelta(days=1)
        return date, _date_key(date)
    if now.strftime("%Y%m%d") < min_key:
        date = _parse_date_key(min_key)
        if not date:
            return None
        for _ in range(7):
            if date.weekday() == target_dow:
                return date, _date_key(date)
            date += timedelta(days=1)
        return date, _date_key(date)
    return None


def _day_distance(a: datetime, b: datetime) -> int:
    return abs((a.date() - b.date()).days)


def _find_fallback_date(conn, now: datetime) -> Optional[Tuple[datetime, str]]:
    if not config.ALLOW_CALENDAR_FALLBACK:
        return None

    min_key, max_key = _calendar_range(conn)
    if min_key and max_key:
        nearest = _find_nearest_in_range(now, min_key, max_key)
        if nearest:
            # Do not fallback to very old/future service days.
            if _day_distance(now, nearest[0]) <= config.CALENDAR_FALLBACK_DAYS:
                return nearest

    for delta in range(1, config.CALENDAR_FALLBACK_DAYS + 1):
        for sign in (-1, 1):
            candidate = now + timedelta(days=sign * delta)
            key = _date_key(candidate)
            active = _active_service_ids(conn, key, candidate.weekday())
            if active:
                return candidate, key
    return None


def get_active_services(conn, now: datetime) -> Tuple[Set[str], datetime, str, bool]:
    date_key = _date_key(now)
    active = _active_service_ids(conn, date_key, now.weekday())
    if active:
        return active, now, date_key, False

    fallback = _find_fallback_date(conn, now)
    if fallback:
        date, key = fallback
        active = _active_service_ids(conn, key, date.weekday())
        return active, date, key, True

    return set(), now, date_key, False


def _filter_headsign(rows, keywords: Optional[List[str]], direction_id: Optional[int]):
    if direction_id is not None:
        return [r for r in rows if r["direction_id"] == direction_id]
    if not keywords:
        return rows
    norm = [normalize_text(k) for k in keywords]
    out = []
    for r in rows:
        headsign = normalize_text(r["trip_headsign"] or "")
        if any(k in headsign for k in norm):
            out.append(r)
    return out


def _has_table(conn, name: str) -> bool:
    rows = query(conn, "SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (name,))
    return bool(rows)


def _next_frequency_departures(
    conn,
    stop_ids: List[str],
    route_ids: List[str],
    service_ids: Set[str],
    now_seconds: int,
    limit: int,
    headsign_keywords: Optional[List[str]],
    direction_id: Optional[int],
) -> Tuple[List[Departure], Set[str]]:
    if not _has_table(conn, "frequencies"):
        return [], set()

    stop_ph = ",".join(["?"] * len(stop_ids))
    route_ph = ",".join(["?"] * len(route_ids))
    service_ph = ",".join(["?"] * len(service_ids))

    sql = f"""
        SELECT f.trip_id, f.start_secs, f.end_secs, f.headway_secs, f.exact_times,
               t.trip_headsign, t.direction_id
        FROM frequencies f
        JOIN trips t ON t.trip_id = f.trip_id
        WHERE t.route_id IN ({route_ph})
          AND t.service_id IN ({service_ph})
    """
    params = list(route_ids) + list(service_ids)
    freq_rows = query(conn, sql, params)
    freq_rows = _filter_headsign(freq_rows, headsign_keywords, direction_id)
    if not freq_rows:
        return [], set()

    freq_trip_ids = {r["trip_id"] for r in freq_rows if (r["exact_times"] or 0) == 0}
    trip_ids = sorted({r["trip_id"] for r in freq_rows})
    trip_ph = ",".join(["?"] * len(trip_ids))

    start_rows = query(
        conn,
        f"""
        SELECT trip_id, MIN(arrival_secs) AS start_secs
        FROM stop_times
        WHERE trip_id IN ({trip_ph})
        GROUP BY trip_id
        """,
        trip_ids,
    )
    trip_start = {r["trip_id"]: r["start_secs"] for r in start_rows}

    stop_rows = query(
        conn,
        f"""
        SELECT trip_id, arrival_secs
        FROM stop_times
        WHERE trip_id IN ({trip_ph})
          AND stop_id IN ({stop_ph})
        """,
        trip_ids + list(stop_ids),
    )
    trip_stop_arrivals = {}
    for r in stop_rows:
        trip_stop_arrivals.setdefault(r["trip_id"], []).append(r["arrival_secs"])

    seen = set()
    out: List[Departure] = []
    for fr in freq_rows:
        if (fr["exact_times"] or 0) == 1:
            continue
        trip_id = fr["trip_id"]
        base_start = trip_start.get(trip_id)
        if base_start is None:
            continue
        offsets = trip_stop_arrivals.get(trip_id)
        if not offsets:
            continue
        start = fr["start_secs"]
        end = fr["end_secs"]
        headway = fr["headway_secs"]
        if headway <= 0:
            continue
        for arr in offsets:
            offset = arr - base_start
            window_start = start + offset
            window_end = end + offset
            if now_seconds > window_end:
                continue
            if now_seconds <= window_start:
                t = window_start
            else:
                k = (now_seconds - window_start + headway - 1) // headway
                t = window_start + k * headway
                if t > window_end:
                    continue
            minutes = int((t - now_seconds) / 60)
            if minutes < 0:
                continue
            if config.LOOKAHEAD_MINUTES > 0 and minutes > config.LOOKAHEAD_MINUTES:
                continue
            key = (t, minutes)
            if key in seen:
                continue
            seen.add(key)
            out.append(Departure(minutes=minutes, time_str=seconds_to_hhmm(t)))

    out.sort(key=lambda d: d.minutes)
    return out[:limit], freq_trip_ids


def next_departures(
    conn,
    stop_ids: List[str],
    route_ids: List[str],
    service_ids: Set[str],
    now_seconds: int,
    limit: int,
    headsign_keywords: Optional[List[str]] = None,
    direction_id: Optional[int] = None,
) -> List[Departure]:
    if not stop_ids or not route_ids or not service_ids:
        return []

    stop_ph = ",".join(["?"] * len(stop_ids))
    route_ph = ",".join(["?"] * len(route_ids))
    service_ph = ",".join(["?"] * len(service_ids))

    fetch_limit = max(limit * 20, limit)
    freq_out, freq_trip_ids = _next_frequency_departures(
        conn,
        stop_ids,
        route_ids,
        service_ids,
        now_seconds,
        limit,
        headsign_keywords,
        direction_id,
    )

    exclude_freq = ""
    if freq_trip_ids:
        placeholders = ",".join(["?"] * len(freq_trip_ids))
        exclude_freq = f"AND t.trip_id NOT IN ({placeholders})"

    sql = f"""
        SELECT st.arrival_secs, t.trip_headsign, t.direction_id
        FROM stop_times st
        JOIN trips t ON t.trip_id = st.trip_id
        WHERE st.stop_id IN ({stop_ph})
          AND t.route_id IN ({route_ph})
          AND t.service_id IN ({service_ph})
          {exclude_freq}
          AND st.arrival_secs >= ?
        ORDER BY st.arrival_secs
        LIMIT {fetch_limit}
    """
    params = list(stop_ids) + list(route_ids) + list(service_ids)
    if freq_trip_ids:
        params += list(freq_trip_ids)
    params += [now_seconds]
    rows = query(conn, sql, params)
    rows = _filter_headsign(rows, headsign_keywords, direction_id)

    out: List[Departure] = []
    for r in rows:
        minutes = int((r["arrival_secs"] - now_seconds) / 60)
        if minutes < 0:
            continue
        if config.LOOKAHEAD_MINUTES > 0 and minutes > config.LOOKAHEAD_MINUTES:
            break
        out.append(Departure(minutes=minutes, time_str=seconds_to_hhmm(r["arrival_secs"])))
        if len(out) >= limit:
            break
    if freq_out:
        out = sorted(out + freq_out, key=lambda d: d.minutes)
        return out[:limit]
    if out:
        return out

    # Fallback: show earliest departures on the next day if no services remain today.
    sql2 = f"""
        SELECT st.arrival_secs, t.trip_headsign, t.direction_id
        FROM stop_times st
        JOIN trips t ON t.trip_id = st.trip_id
        WHERE st.stop_id IN ({stop_ph})
          AND t.route_id IN ({route_ph})
          AND t.service_id IN ({service_ph})
        ORDER BY st.arrival_secs
        LIMIT {fetch_limit}
    """
    rows2 = query(conn, sql2, params[:-1])  # reuse same params without now_seconds
    rows2 = _filter_headsign(rows2, headsign_keywords, direction_id)
    for r in rows2:
        minutes = int((r["arrival_secs"] + 24 * 3600 - now_seconds) / 60)
        if minutes < 0:
            continue
        out.append(
            Departure(
                minutes=minutes,
                time_str=seconds_to_hhmm(r["arrival_secs"]),
                is_next_day=True,
            )
        )
        if len(out) >= limit:
            break
    return out


def get_now(tz_name: str) -> datetime:
    if ZoneInfo is None:
        return datetime.now()
    return datetime.now(ZoneInfo(tz_name))
