# AyrilikPano

Minimal, station-board style metro display for Ayrilikcesmesi (Marmaray + M4).
GTFS-based, offline-first, and Raspberry Pi friendly.

**Suggested repo name:** `ayrilik-pano`

## What this is
- Small home display that feels like a station panel
- Uses **static GTFS** (no scraping, no real-time dependency)
- Calculates "minutes left" from schedules
- Works in terminal now; ready for E-Ink later

## How it works (high level)
1) Download GTFS from IBB CKAN
2) Import to SQLite
3) Resolve stop_id for Ayrilikcesmesi
4) Use stop_times + frequencies to compute next departures
5) Render to terminal (or PNG for E-Ink)

## Quick start (terminal mode)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r metro_display/requirements.txt
python3 -m metro_display.terminal
```

## Configuration
Edit `metro_display/config.py`:
- `STATION_NAME`: default `Ayrilik Cesmesi`
- `LINES`: line definitions and **fixed stop_ids** for accuracy
  - Marmaray stop_id: `12258`
  - M4 stop_id: `94911`
- `DEPARTURES_PER_DIRECTION`: how many upcoming trips
- `LOOKAHEAD_MINUTES`: max minutes to show (set 0 to disable)
- `GTFS_ZIP_URL` or `CKAN_BASE_URL` + `CKAN_DATASET_ID`
- `DISPLAY_DRIVER`: `png` or `waveshare`
- `REFRESH_SECONDS`: refresh interval

## Data refresh
GTFS is cached. Default refresh period is 24h.
- To force refresh, delete the cached zip:
```bash
rm -f metro_display/data/gtfs.zip
python3 -m metro_display.terminal
```

## Reliability notes (important)
- This is **schedule-based**. No live delays/vehicle locations.
- The public GTFS calendar in IBB currently ends at **2024-12-31**.
  The app falls back to the closest available weekday when running in 2026.
- Marmaray schedules in this dataset are defined by **frequencies**; these are now supported.

## Troubleshooting
- "Remote end closed connection without response": temporary server/network issue.
  The app retries and uses cached GTFS if available.
- If you see "Yarin", it means no more trips remain today.
  Increase `LOOKAHEAD_MINUTES` or check if GTFS is outdated.
- If Turkish characters look broken, set terminal encoding:
```bash
PYTHONIOENCODING=utf-8 python3 -m metro_display.terminal
```

## Hardware (later)
Target device: Raspberry Pi Zero 2 W + 7-7.5" E-Ink
- Set `DISPLAY_DRIVER = "waveshare"`
- Run `python3 -m metro_display.app`
- Latest render saved to `metro_display/data/last.png` in dev mode

## Repo structure
- `metro_display/` main Python app
- `metro_display/gtfs/` downloader + importer
- `metro_display/schedule/` next-trip logic
- `metro_display/render/` layout + drawing
- `metro_display/systemd/` service file for auto-start

## Suggested next steps
- Add weekly-pattern fallback for expired calendars (more realistic in 2026)
- Add "last updated" badge in terminal
- Optional: real-time overlay if a GTFS-RT feed becomes available
