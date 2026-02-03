"""Project configuration.

All values are explicit and editable. No hidden assumptions.
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# --- GTFS source ---
# Option A: provide a direct GTFS zip URL.
GTFS_ZIP_URL = ""

# Option B: resolve via CKAN (recommended for IBB/B40 portals).
CKAN_BASE_URL = "https://opendata.b40cities.org/tr/api/3/action"
CKAN_DATASET_ID = "toplu-ulasim-gtfs-verisi"

GTFS_CACHE_HOURS = 24
# IBB GTFS feeds are typically Windows-1254 encoded.
GTFS_ENCODING = "windows-1254"

# --- Database ---
DB_PATH = DATA_DIR / "gtfs.sqlite3"

# --- Display / Refresh ---
TIMEZONE = "Europe/Istanbul"
REFRESH_SECONDS = 60
DEPARTURES_PER_DIRECTION = 2
LOOKAHEAD_MINUTES = 120

# If True, allow fallback to the nearest calendar date when today has no service.
ALLOW_CALENDAR_FALLBACK = True
CALENDAR_FALLBACK_DAYS = 14

# --- Station ---
STATION_NAME = "Ayrılık Çeşmesi"

# --- Line definitions ---
# Use ASCII by default; normalize() handles Turkish characters.
LINES = [
    {
        "name": "MARMARAY",
        "route_keywords": ["Marmaray"],
        # Fixed stop_id for Ayrılıkçeşme Marmaray (prevents ambiguous stop matches).
        "stop_ids": ["12258"],
        "directions": [
            {"label": "Avrupa", "headsign_keywords": ["Halkalı", "Zeytinburnu", "Bahçeşehir"]},
            {"label": "Anadolu", "headsign_keywords": ["Gebze", "Söğütlüçeşme"]},
        ],
    },
    {
        "name": "M4",
        "route_keywords": ["M4"],
        # Fixed stop_id for Ayrılık Çeşmesi M4.
        "stop_ids": ["94911"],
        "directions": [
            {"label": "Kadıköy", "headsign_keywords": ["Kadıköy"]},
            {"label": "Sabiha", "headsign_keywords": ["Tavşantepe"]},
        ],
    },
]

# --- Rendering ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 480
BACKGROUND_COLOR = 1  # 1=white in Pillow "1" mode
FOREGROUND_COLOR = 0  # 0=black

FONT_PATH = ""  # e.g. "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_TITLE_SIZE = 36
FONT_SECTION_SIZE = 24
FONT_ROW_SIZE = 28
FONT_TIME_SIZE = 20

# --- Display driver ---
# Set to "waveshare" when running on hardware.
DISPLAY_DRIVER = "png"  # "png" | "waveshare"
OUTPUT_PNG_PATH = DATA_DIR / "last.png"
