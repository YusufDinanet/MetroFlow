# AyrilikPano

Live-first station-style display for Ayrilik Cesmesi:
- Marmaray + M4 departure minutes
- Optional GTFS fallback
- Optional Ramadan footer (imsak / iftar + remaining time)

Designed for Raspberry Pi and 7-inch screens (800x480).

## Current status
- M4 source: Metro Istanbul live timetable endpoint
- Marmaray source: TCDD live timetable endpoint
- GTFS is used only as fallback when configured
- Board note can hide old/expired GTFS text (`SHOW_STATUS_NOTE=False`)
- Ramadan footer is rendered at the bottom of the same screen

## Quick start
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r metro_display/requirements.txt
python3 -m metro_display.terminal
```

Image render mode:
```bash
python3 -m metro_display.app
```

Latest image output:
```text
metro_display/data/last.png
```

## Data sources
- M4:
  - `https://www.metro.istanbul/SeferDurumlari/SeferDetaylari`
  - `https://www.metro.istanbul/SeferDurumlari/AJAXSeferGetir`
- Marmaray:
  - `https://www.tcddtasimacilik.gov.tr/marmaray/tr/gunluk_tren_saatleri`
  - `https://api.tcddtasimacilik.gov.tr/api/SubPages/GetTransportationTrainsGroupwithHours?marmaray=true`
- Ramadan timings:
  - `https://api.aladhan.com/v1/timingsByCity`

## Configuration
Edit `metro_display/config.py`.

Core:
- `STATION_NAME`
- `REFRESH_SECONDS`
- `DEPARTURES_PER_DIRECTION`
- `LOOKAHEAD_MINUTES`
- `TIMEZONE`

Live/fallback:
- `USE_LIVE_SOURCES`
- `LIVE_FALLBACK_TO_GTFS`
- `SHOW_STATUS_NOTE`
- `ALLOW_CALENDAR_FALLBACK`
- `CALENDAR_FALLBACK_DAYS`

Line and stop mapping:
- `LINES`
  - Marmaray fixed stop_id: `12258`
  - M4 fixed stop_id: `94911`

Display:
- `DISPLAY_DRIVER` (`png` or `waveshare`)
- `SCREEN_WIDTH` / `SCREEN_HEIGHT` (default `800x480`)
- `TERMINAL_WIDTH` / `TERMINAL_LABEL_WIDTH`
- `FONT_PATH` (recommended for Turkish characters on image render)

Ramadan footer:
- `SHOW_RAMADAN_PANEL`
- `RAMADAN_CITY`
- `RAMADAN_COUNTRY`
- `RAMADAN_METHOD`
- `RAMADAN_TARGET_DATE`
  - `YYYY-MM-DD` -> fixed day (example: `2026-02-20`)
  - empty string -> auto use today

## 7-inch usage
For 7-inch HDMI terminal:
- keep `SCREEN_WIDTH = 800`, `SCREEN_HEIGHT = 480`
- run terminal full screen
- tune `TERMINAL_WIDTH` (for example `92`)

For 7-inch e-ink:
- set `DISPLAY_DRIVER = "waveshare"`
- run `python3 -m metro_display.app`

## Notes on reliability
- Live sources are timetable-based, not vehicle GPS delay data.
- If a live source fails and GTFS fallback is enabled, departures still render from local GTFS.
- If fallback data is old but you do not want warning text, keep `SHOW_STATUS_NOTE=False`.
- Ramadan footer has API fallback behavior and can show `veri alinamadi` on fetch errors.

## Maintenance
Force GTFS refresh:
```bash
rm -f metro_display/data/gtfs.zip
python3 -m metro_display.terminal
```

## Project layout
- `metro_display/app.py`: main loop and model builder
- `metro_display/live_sources.py`: M4 + Marmaray live providers
- `metro_display/ramadan.py`: imsak/iftar footer module
- `metro_display/render/`: image rendering
- `metro_display/terminal.py`: terminal board output
- `metro_display/gtfs/`: GTFS download/import
- `metro_display/systemd/`: service example
