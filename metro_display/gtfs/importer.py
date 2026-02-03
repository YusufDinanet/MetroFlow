"""GTFS zip importer into SQLite."""
import csv
import sqlite3
import zipfile
from pathlib import Path

from .. import config
from .parser import gtfs_time_to_seconds

REQUIRED_FILES = {
    "stops.txt",
    "routes.txt",
    "trips.txt",
    "stop_times.txt",
    "calendar.txt",
}

OPTIONAL_FILES = {
    "calendar_dates.txt",
    "frequencies.txt",
}


def _read_csv(zf: zipfile.ZipFile, name: str, encoding: str):
    with zf.open(name) as f:
        text = f.read().decode(encoding, errors="replace")
    return csv.DictReader(text.splitlines())


def _create_schema(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.executescript(
        """
        DROP TABLE IF EXISTS stops;
        DROP TABLE IF EXISTS routes;
        DROP TABLE IF EXISTS trips;
        DROP TABLE IF EXISTS stop_times;
        DROP TABLE IF EXISTS calendar;
        DROP TABLE IF EXISTS calendar_dates;
        DROP TABLE IF EXISTS meta;

        CREATE TABLE stops (
            stop_id TEXT PRIMARY KEY,
            stop_name TEXT,
            stop_lat REAL,
            stop_lon REAL
        );

        CREATE TABLE routes (
            route_id TEXT PRIMARY KEY,
            route_short_name TEXT,
            route_long_name TEXT
        );

        CREATE TABLE trips (
            trip_id TEXT PRIMARY KEY,
            route_id TEXT,
            service_id TEXT,
            trip_headsign TEXT,
            direction_id INTEGER
        );

        CREATE TABLE stop_times (
            trip_id TEXT,
            stop_id TEXT,
            stop_sequence INTEGER,
            arrival_secs INTEGER,
            departure_secs INTEGER
        );

        CREATE TABLE calendar (
            service_id TEXT PRIMARY KEY,
            monday INTEGER,
            tuesday INTEGER,
            wednesday INTEGER,
            thursday INTEGER,
            friday INTEGER,
            saturday INTEGER,
            sunday INTEGER,
            start_date TEXT,
            end_date TEXT
        );

        CREATE TABLE calendar_dates (
            service_id TEXT,
            date TEXT,
            exception_type INTEGER
        );

        CREATE TABLE frequencies (
            trip_id TEXT,
            start_secs INTEGER,
            end_secs INTEGER,
            headway_secs INTEGER,
            exact_times INTEGER
        );

        CREATE TABLE meta (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )
    conn.commit()


def _create_indexes(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_stop_times_stop_id_arrival
            ON stop_times(stop_id, arrival_secs);
        CREATE INDEX IF NOT EXISTS idx_stop_times_trip_id
            ON stop_times(trip_id);
        CREATE INDEX IF NOT EXISTS idx_trips_route_id
            ON trips(route_id);
        CREATE INDEX IF NOT EXISTS idx_trips_service_id
            ON trips(service_id);
        CREATE INDEX IF NOT EXISTS idx_frequencies_trip_id
            ON frequencies(trip_id);
        """
    )
    conn.commit()


def import_gtfs(zip_path: Path, db_path: Path) -> None:
    temp_db = db_path.with_suffix(".tmp")
    if temp_db.exists():
        temp_db.unlink()

    conn = sqlite3.connect(str(temp_db))
    conn.execute("PRAGMA journal_mode = OFF")
    conn.execute("PRAGMA synchronous = OFF")
    _create_schema(conn)

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = set(zf.namelist())
        missing = REQUIRED_FILES - names
        if missing:
            raise RuntimeError(f"Missing GTFS files: {sorted(missing)}")

        stops = []
        for row in _read_csv(zf, "stops.txt", config.GTFS_ENCODING):
            stops.append(
                (
                    row.get("stop_id"),
                    row.get("stop_name"),
                    row.get("stop_lat"),
                    row.get("stop_lon"),
                )
            )
        conn.executemany("INSERT INTO stops VALUES (?,?,?,?)", stops)

        routes = []
        for row in _read_csv(zf, "routes.txt", config.GTFS_ENCODING):
            routes.append(
                (
                    row.get("route_id"),
                    row.get("route_short_name"),
                    row.get("route_long_name"),
                )
            )
        conn.executemany("INSERT INTO routes VALUES (?,?,?)", routes)

        trips = []
        for row in _read_csv(zf, "trips.txt", config.GTFS_ENCODING):
            trips.append(
                (
                    row.get("trip_id"),
                    row.get("route_id"),
                    row.get("service_id"),
                    row.get("trip_headsign"),
                    int(row.get("direction_id") or 0),
                )
            )
        conn.executemany("INSERT INTO trips VALUES (?,?,?,?,?)", trips)

        stop_times = []
        batch_size = 20000
        for row in _read_csv(zf, "stop_times.txt", config.GTFS_ENCODING):
            arr = gtfs_time_to_seconds(row.get("arrival_time"))
            dep = gtfs_time_to_seconds(row.get("departure_time"))
            stop_times.append(
                (
                    row.get("trip_id"),
                    row.get("stop_id"),
                    int(row.get("stop_sequence") or 0),
                    arr,
                    dep,
                )
            )
            if len(stop_times) >= batch_size:
                conn.executemany("INSERT INTO stop_times VALUES (?,?,?,?,?)", stop_times)
                stop_times.clear()
        if stop_times:
            conn.executemany("INSERT INTO stop_times VALUES (?,?,?,?,?)", stop_times)

        calendar = []
        for row in _read_csv(zf, "calendar.txt", config.GTFS_ENCODING):
            calendar.append(
                (
                    row.get("service_id"),
                    int(row.get("monday") or 0),
                    int(row.get("tuesday") or 0),
                    int(row.get("wednesday") or 0),
                    int(row.get("thursday") or 0),
                    int(row.get("friday") or 0),
                    int(row.get("saturday") or 0),
                    int(row.get("sunday") or 0),
                    row.get("start_date"),
                    row.get("end_date"),
                )
            )
        conn.executemany("INSERT INTO calendar VALUES (?,?,?,?,?,?,?,?,?,?)", calendar)

        cal_dates = []
        if "calendar_dates.txt" in names:
            for row in _read_csv(zf, "calendar_dates.txt", config.GTFS_ENCODING):
                cal_dates.append(
                    (
                        row.get("service_id"),
                        row.get("date"),
                        int(row.get("exception_type") or 0),
                    )
                )
        if cal_dates:
            conn.executemany("INSERT INTO calendar_dates VALUES (?,?,?)", cal_dates)

        frequencies = []
        if "frequencies.txt" in names:
            for row in _read_csv(zf, "frequencies.txt", config.GTFS_ENCODING):
                start = gtfs_time_to_seconds(row.get("start_time"))
                end = gtfs_time_to_seconds(row.get("end_time"))
                headway = int(row.get("headway_secs") or 0)
                exact = int(row.get("exact_times") or 0)
                if start is None or end is None or headway <= 0:
                    continue
                frequencies.append((row.get("trip_id"), start, end, headway, exact))
        if frequencies:
            conn.executemany("INSERT INTO frequencies VALUES (?,?,?,?,?)", frequencies)

    _create_indexes(conn)

    conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", ("gtfs_zip", str(zip_path)))
    conn.commit()
    conn.close()

    temp_db.replace(db_path)
