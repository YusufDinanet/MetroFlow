# Metro Display (GTFS-based)

GTFS schedule display for Raspberry Pi / E-Ink. Offline-first.

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
- `GTFS_ZIP_URL` or `CKAN_BASE_URL` + `CKAN_DATASET_ID`
- `GTFS_ENCODING` (IBB uses windows-1254)
- `STATION_NAME`
- `LINES` (direction keywords + fixed stop_ids)
- `DISPLAY_DRIVER` (`png` or `waveshare`)

## Requirements
- Python 3.6+
- Pillow (`pip install pillow`)
- waveshare_epd (only on hardware)

## Notes
- Uses stop_times + frequencies
- Schedule-based only (no live delays)
