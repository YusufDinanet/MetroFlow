"""Main loop for the metro display."""
import time
from dataclasses import dataclass
from typing import Dict, List

from . import config
from .db import get_connection
from .gtfs.downloader import ensure_gtfs_zip
from .gtfs.importer import import_gtfs
from .render.draw import DirectionRow, LineBlock, ScreenModel, render_screen
from .schedule.next_trips import Departure, get_active_services, get_now, next_departures
from .schedule.resolver import resolve_route_ids, resolve_stop_ids


@dataclass
class LineCache:
    route_ids: List[str]
    stop_ids: List[str]

_CACHE: Dict[str, LineCache] = {}

def _ensure_db() -> None:
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
    service_ids, service_date, date_key, fallback = get_active_services(conn, now)

    service_midnight = service_date.replace(hour=0, minute=0, second=0, microsecond=0)
    service_now = service_midnight.replace(hour=now.hour, minute=now.minute, second=now.second)
    now_seconds = int((service_now - service_midnight).total_seconds())

    note = None
    if fallback:
        note = f"Schedule date: {date_key}"

    line_blocks: List[LineBlock] = []

    for line in config.LINES:
        line_name = line["name"]
        route_ids = _CACHE.get(line_name, LineCache([], [])).route_ids
        stop_ids = _CACHE.get(line_name, LineCache([], [])).stop_ids

        if not route_ids:
            route_ids = resolve_route_ids(conn, line.get("route_keywords", []))
        override_stop_ids = line.get("stop_ids")
        if override_stop_ids:
            stop_ids = list(override_stop_ids)
        elif not stop_ids:
            stop_ids = resolve_stop_ids(conn, config.STATION_NAME, route_ids)
        _CACHE[line_name] = LineCache(route_ids=route_ids, stop_ids=stop_ids)

        direction_rows: List[DirectionRow] = []
        for direction in line.get("directions", []):
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

    return ScreenModel(title=config.STATION_NAME.upper(), updated_at=now, lines=line_blocks, note=note)


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
