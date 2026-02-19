"""Main loop for the metro display."""
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List

from . import config
from .db import get_connection, query
from .gtfs.downloader import ensure_gtfs_zip
from .gtfs.importer import import_gtfs
from .gtfs.parser import normalize_text
from .live_sources import fetch_live_line_departures
from .ramadan import get_ramadan_footer_lines
from .render.draw import DirectionRow, LineBlock, ScreenModel, render_screen
from .schedule.next_trips import Departure, get_active_services, get_now, next_departures
from .schedule.resolver import resolve_route_ids, resolve_stop_ids


@dataclass
class LineCache:
    route_ids: List[str]
    stop_ids: List[str]

_CACHE: Dict[str, LineCache] = {}


def _schedule_fallback_note(service_date, now) -> str:
    age_days = (now.date() - service_date.date()).days
    age_suffix = f", {age_days}d old" if age_days > 0 else ""
    return f"GTFS fallback: {service_date:%Y-%m-%d} ({service_date:%a}{age_suffix})"


def _parse_date_key(key: str):
    if not key or len(key) != 8:
        return None
    try:
        return datetime(int(key[0:4]), int(key[4:6]), int(key[6:8]))
    except ValueError:
        return None


def _no_service_note(conn, now: datetime) -> str:
    rows = query(conn, "SELECT MIN(start_date) AS min_start, MAX(end_date) AS max_end FROM calendar")
    if not rows:
        return "No active service (calendar missing)"

    min_date = _parse_date_key(rows[0]["min_start"])
    max_date = _parse_date_key(rows[0]["max_end"])

    if max_date and now.date() > max_date.date():
        age_days = (now.date() - max_date.date()).days
        return f"GTFS expired: {max_date:%Y-%m-%d} ({age_days}d old)"
    if min_date and now.date() < min_date.date():
        lead_days = (min_date.date() - now.date()).days
        return f"GTFS starts at {min_date:%Y-%m-%d} ({lead_days}d ahead)"
    return "No active service for this date"


def _line_uses_live(line_name: str) -> bool:
    if not config.USE_LIVE_SOURCES:
        return False
    norm = normalize_text(line_name)
    return norm == "m4" or "marmaray" in norm


def _requires_gtfs() -> bool:
    if config.LIVE_FALLBACK_TO_GTFS:
        return True
    for line in config.LINES:
        if not _line_uses_live(line["name"]):
            return True
    return False


def _ensure_db() -> None:
    if not _requires_gtfs():
        return
    zip_path = config.DATA_DIR / "gtfs.zip"
    ensure_gtfs_zip(zip_path)
    if not config.DB_PATH.exists() or zip_path.stat().st_mtime > config.DB_PATH.stat().st_mtime:
        import_gtfs(zip_path, config.DB_PATH)


def _format_departure(dep: Departure) -> str:
    if dep.is_next_day:
        return f"Yarın {dep.time_str}"
    return f"{dep.minutes} dk {dep.time_str}"


def _build_model(conn) -> ScreenModel:
    now = get_now(config.TIMEZONE)
    note = None
    footer_lines: List[str] = []
    gtfs_ctx = None

    def ensure_gtfs_ctx():
        nonlocal gtfs_ctx, note
        if gtfs_ctx is not None:
            return gtfs_ctx

        service_ids, service_date, _date_key, fallback = get_active_services(conn, now)
        service_midnight = service_date.replace(hour=0, minute=0, second=0, microsecond=0)
        service_now = service_midnight.replace(hour=now.hour, minute=now.minute, second=now.second)
        now_seconds = int((service_now - service_midnight).total_seconds())
        gtfs_ctx = (service_ids, now_seconds)

        if config.SHOW_STATUS_NOTE:
            if fallback:
                note = _schedule_fallback_note(service_date, now)
            elif not service_ids:
                note = _no_service_note(conn, now)
        return gtfs_ctx

    line_blocks: List[LineBlock] = []

    for line in config.LINES:
        line_name = line["name"]
        cache_item = _CACHE.get(line_name, LineCache([], []))
        route_ids = cache_item.route_ids
        stop_ids = cache_item.stop_ids

        use_live_line = _line_uses_live(line_name)
        live_departures = {}
        if use_live_line:
            try:
                live_departures = fetch_live_line_departures(
                    line_name=line_name,
                    station_name=config.STATION_NAME,
                    now=now,
                    limit=config.DEPARTURES_PER_DIRECTION,
                )
            except Exception:  # noqa: BLE001
                live_departures = {}

        direction_rows: List[DirectionRow] = []
        for direction in line.get("directions", []):
            departures = []

            live_key = normalize_text(direction["label"])
            if live_departures:
                departures = live_departures.get(live_key, [])

            use_gtfs_fallback = (not use_live_line) or config.LIVE_FALLBACK_TO_GTFS
            if not departures and use_gtfs_fallback:
                if not route_ids:
                    route_ids = resolve_route_ids(conn, line.get("route_keywords", []))
                override_stop_ids = line.get("stop_ids")
                if override_stop_ids:
                    stop_ids = list(override_stop_ids)
                elif not stop_ids:
                    stop_ids = resolve_stop_ids(conn, config.STATION_NAME, route_ids)
                _CACHE[line_name] = LineCache(route_ids=route_ids, stop_ids=stop_ids)

                service_ids, now_seconds = ensure_gtfs_ctx()
                if service_ids:
                    headsign_keywords = direction.get("headsign_keywords")
                    direction_id = direction.get("direction_id")
                    departures = next_departures(
                        conn,
                        stop_ids,
                        route_ids,
                        service_ids,
                        now_seconds,
                        config.DEPARTURES_PER_DIRECTION,
                        headsign_keywords=headsign_keywords,
                        direction_id=direction_id,
                    )

            formatted = [_format_departure(dep) for dep in departures]
            direction_rows.append(DirectionRow(label=direction["label"], departures=formatted))

        line_blocks.append(LineBlock(name=line_name, directions=direction_rows))

    try:
        footer_lines = get_ramadan_footer_lines(now)
    except Exception:  # noqa: BLE001
        footer_lines = ["Ramazan: veri alinamadi"]

    return ScreenModel(
        title=config.STATION_NAME.upper(),
        updated_at=now,
        lines=line_blocks,
        note=note,
        footer_lines=footer_lines,
    )


def _save_image(img) -> None:
    config.OUTPUT_PNG_PATH.parent.mkdir(parents=True, exist_ok=True)
    img.save(config.OUTPUT_PNG_PATH)


def _get_display():
    if config.DISPLAY_DRIVER == "waveshare":
        from .display.epd_waveshare import WaveshareEPD

        return WaveshareEPD()
    return None


def main() -> None:
    _ensure_db()
    display = _get_display()

    while True:
        with get_connection() as conn:
            model = _build_model(conn)
        img = render_screen(model)
        if display:
            display.display(img)
        else:
            _save_image(img)
        time.sleep(config.REFRESH_SECONDS)


if __name__ == "__main__":
    main()
