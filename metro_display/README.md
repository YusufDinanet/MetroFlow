# Metro Display

Live-first metro board renderer used by this project.

## Run
Terminal mode:
```bash
python3 -m metro_display.terminal
```

Image mode:
```bash
python3 -m metro_display.app
```

Output image path:
```text
metro_display/data/last.png
```

## What it shows
- Marmaray departure minutes (Avrupa / Anadolu)
- M4 departure minutes (Kadikoy / Sabiha)
- Optional Ramadan footer:
  - imsak
  - iftar
  - remaining time

## Config keys
Edit `metro_display/config.py`:
- `STATION_NAME`
- `USE_LIVE_SOURCES`
- `LIVE_FALLBACK_TO_GTFS`
- `SHOW_STATUS_NOTE`
- `M4_TIMETABLE_PAGE_URL` / `M4_TIMETABLE_AJAX_URL`
- `MARMARAY_TIMETABLE_PAGE_URL` / `MARMARAY_API_URL`
- `SHOW_RAMADAN_PANEL`
- `RAMADAN_TARGET_DATE`
- `RAMADAN_CITY` / `RAMADAN_COUNTRY` / `RAMADAN_METHOD`
- `DISPLAY_DRIVER` (`png` / `waveshare`)
- `SCREEN_WIDTH` / `SCREEN_HEIGHT`

## Notes
- Live sources are timetable APIs, not GPS delay feeds.
- GTFS is fallback only when enabled.
- If image render has Turkish glyph issues, set `FONT_PATH` to a TTF that supports Turkish.
