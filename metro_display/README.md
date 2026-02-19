# Metro Display (Live + GTFS fallback)

Live timetable display for Raspberry Pi / E-Ink.

## Run (terminal)
```bash
python3 -m metro_display.terminal
```

## Run (image render)
```bash
python3 -m metro_display.app
```

Latest PNG:
```
metro_display/data/last.png
```

## Configuration
Edit `metro_display/config.py`:
- `USE_LIVE_SOURCES` / `LIVE_FALLBACK_TO_GTFS`
- `M4_TIMETABLE_PAGE_URL` / `M4_TIMETABLE_AJAX_URL`
- `MARMARAY_TIMETABLE_PAGE_URL` / `MARMARAY_API_URL`
- `SHOW_RAMADAN_PANEL` / `RAMADAN_TARGET_DATE`
- `RAMADAN_CITY` / `RAMADAN_COUNTRY` / `RAMADAN_METHOD`
- GTFS source settings (optional fallback)
- `STATION_NAME`
- `LINES` (direction keywords + fixed stop_ids)
- `DISPLAY_DRIVER` (`png` or `waveshare`)

## Requirements
- Python 3.6+
- Pillow (`pip install pillow`)
- waveshare_epd (only on hardware)

## Notes
- M4 uses Metro Istanbul timetable endpoint
- Marmaray uses TCDD timetable endpoint
- GTFS is used only as fallback when enabled
