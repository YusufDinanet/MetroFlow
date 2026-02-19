# AyrilikPano

Minimal, station-board style metro display for Ayrilikcesmesi (Marmaray + M4).
Live-first, Raspberry Pi friendly.

**Suggested repo name:** `ayrilik-pano`

## What this is
- Small home display that feels like a station panel
- Uses **official live web sources** for M4 and Marmaray
- Calculates "minutes left" from returned departure times
- Works in terminal now; ready for E-Ink later

## How it works (high level)
1) M4: query Metro Istanbul timetable endpoint
2) Marmaray: query TCDD timetable endpoint
3) Parse station-specific departures for Ayrilikcesmesi
4) Render to terminal (or PNG for E-Ink)

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
- `DISPLAY_DRIVER`: `png` or `waveshare`
- `REFRESH_SECONDS`: refresh interval
- `TERMINAL_WIDTH`: terminal panel width (`0` = auto detect)
- `TERMINAL_LABEL_WIDTH`: direction label column width
- `USE_LIVE_SOURCES`: live providers on/off
- `LIVE_FALLBACK_TO_GTFS`: fallback to GTFS if live calls fail
- `M4_TIMETABLE_PAGE_URL` + `M4_TIMETABLE_AJAX_URL`
- `MARMARAY_TIMETABLE_PAGE_URL` + `MARMARAY_API_URL`
- `SHOW_RAMADAN_PANEL`: show/hide imsak-iftar footer
- `RAMADAN_TARGET_DATE`: fixed date (`YYYY-MM-DD`) or empty for today
- `RAMADAN_CITY` / `RAMADAN_COUNTRY` / `RAMADAN_METHOD`

## Data refresh
Live calls are fetched each refresh cycle (`REFRESH_SECONDS`).
If GTFS fallback is enabled, GTFS cache is still used.
- To force GTFS refresh:
```bash
rm -f metro_display/data/gtfs.zip
python3 -m metro_display.terminal
```

## Reliability notes (important)
- M4 source: Metro Istanbul `SeferDurumlari/AJAXSeferGetir`
- Marmaray source: TCDD `GetTransportationTrainsGroupwithHours`
- Live sources are still timetable-based (no delay/vehicle GPS feed).
- If live source fails and `LIVE_FALLBACK_TO_GTFS=True`, app falls back to local GTFS.
- If `SHOW_STATUS_NOTE=False`, fallback/expiry text is hidden on board.

## Troubleshooting
- Network/API errors can be temporary.
  Keep fallback enabled for resilience.
- If you see "Yarin", it means no more trips remain today.
  This is expected around service end.
- If Turkish characters look broken, set terminal encoding:
```bash
PYTHONIOENCODING=utf-8 python3 -m metro_display.terminal
```

## Hardware (later)
Target device: Raspberry Pi Zero 2 W + 7-7.5" E-Ink
- Set `DISPLAY_DRIVER = "waveshare"`
- Run `python3 -m metro_display.app`
- Latest render saved to `metro_display/data/last.png` in dev mode

For a 7" HDMI terminal screen:
- Keep `SCREEN_WIDTH = 800` and `SCREEN_HEIGHT = 480`
- Run terminal fullscreen and tune `TERMINAL_WIDTH` (example: `92`)

## Repo structure
- `metro_display/` main Python app
- `metro_display/gtfs/` downloader + importer
- `metro_display/schedule/` next-trip logic
- `metro_display/render/` layout + drawing
- `metro_display/systemd/` service file for auto-start

## Suggested next steps
- Add line health indicators (live source ok/fallback mode)
- Add "last updated" badge in terminal
- Optional: real-time overlay if a GTFS-RT feed becomes available
