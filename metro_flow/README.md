# Metro Flow

Canli metro panosu motoru (M4 + Marmaray + Ramazan paneli).

## Modlar
- `python -m metro_flow.desktop`
  - 1024x600 profesyonel dashboard UI
  - Ana panellerde destination + dakika kolonlari
- `python -m metro_flow.terminal`
  - terminal odakli gorunum
- `python -m metro_flow.app`
  - PNG/E-Ink render (`metro_flow/data/last.png`)

## Gereksinimler
- Python `3.11+`
- `pip install -r metro_flow/requirements.txt`
- GUI icin `tkinter`:
  - macOS: `brew install python-tk@3.11`
  - Linux: `sudo apt install python3-tk`

## Baslangic
```bash
source .venv/bin/activate
python -m metro_flow.desktop
```

Raspberry Pi:
```bash
cd /home/<user>/Desktop/<project_root>
source .venv/bin/activate
export DISPLAY=:0
export XAUTHORITY=/home/<user>/.Xauthority
PYTHONPATH="$(pwd)" .venv/bin/python -m metro_flow.desktop
```

## Veri Akisi
- M4: Metro Istanbul timetable endpoint
- Marmaray: TCDD timetable endpoint
- Ramazan: Aladhan timings endpoint
- `LIVE_FALLBACK_TO_GTFS=True` ise canli hata durumunda GTFS fallback devrede kalir

## Ana Ayarlar (`config.py`)
- Genel: `STATION_NAME`, `TIMEZONE`, `REFRESH_SECONDS`
- Canli/Fallback: `USE_LIVE_SOURCES`, `LIVE_FALLBACK_TO_GTFS`, `SHOW_STATUS_NOTE`
- M4 kaynak secimi: `M4_TIMETABLE_MODE` (`auto`/`live`/`planned`)
- M4 auto esik: `M4_LIVE_GAP_USE_PLANNED_MINUTES`
- Ramazan: `SHOW_RAMADAN_PANEL`, `RAMADAN_TARGET_DATE`
- Desktop: `DESKTOP_WIDTH`, `DESKTOP_HEIGHT`, `DESKTOP_FULLSCREEN`, `DESKTOP_FONT_FAMILY`
- Desktop: `DESKTOP_SHOW_TIME_AFTER_MINUTES` (ornek: `30`)
- Terminal: `TERMINAL_WIDTH`, `TERMINAL_USE_UNICODE`

Ramazan paneli yenileme:
- Kalan sure arayuzde her `DESKTOP_UI_TICK_SECONDS` (varsayilan `60`) ile yenilenir.
- Metro/Marmaray API verisi her `REFRESH_SECONDS` (varsayilan `60`) dongusunde yenilenir.
- `RAMADAN_TARGET_DATE=\"\"` ise bugunun tarihi kullanilir (onerilen).
- Sabit tarih verilirse panel o tarihe kilitlenir.
- Gecmise sabitlenmis tarih verilse bile sistem bugune doner.
- Hicri ay Ramazan (9) bittikten sonra alt panel otomatik gizlenir.

## Notlar
- Bu paket `urllib` kullandigi icin `requests` gerekmez.
- `tkinter` pip paketi degildir; sistemden kurulmalidir.
- Desktop modda kiosk acilis vardir: fare gizlenir, `Esc` fullscreen cikis, `q` uygulama cikis.

## Lisans
Bu proje `GNU General Public License v3.0 or later (GPL-3.0-or-later)` ile lisanslanmistir.
Detaylar icin `../LICENSE` dosyasina bakin.
