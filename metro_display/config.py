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
TERMINAL_WIDTH = 0  # 0 = auto-detect terminal width
TERMINAL_LABEL_WIDTH = 10

# --- Live sources (M4 + Marmaray) ---
USE_LIVE_SOURCES = True
LIVE_FALLBACK_TO_GTFS = True  # If live fails, fallback to local GTFS.
LIVE_TIMEOUT_SECONDS = 20
LIVE_META_CACHE_SECONDS = 6 * 3600
LIVE_DAY_WRAP_THRESHOLD_MINUTES = 180

# Metro Istanbul (M4)
M4_TIMETABLE_PAGE_URL = "https://www.metro.istanbul/SeferDurumlari/SeferDetaylari"
M4_TIMETABLE_AJAX_URL = "https://www.metro.istanbul/SeferDurumlari/AJAXSeferGetir"

# TCDD Marmaray
MARMARAY_TIMETABLE_PAGE_URL = "https://www.tcddtasimacilik.gov.tr/marmaray/tr/gunluk_tren_saatleri"
MARMARAY_API_URL = "https://api.tcddtasimacilik.gov.tr/api/SubPages/GetTransportationTrainsGroupwithHours?marmaray=true"
MARMARAY_API_BASIC_TOKEN = "aXNfYmFzaWNfdXNlcjppczJvMjMh"
MARMARAY_TRAIN_CODE_PREFIX = "000001"
MARMARAY_EUROPE_KEYWORDS = [
    "Halkalı",
    "Ataköy",
    "Zeytinburnu",
    "Kazlıçeşme",
    "Marmaray Yenikapı",
    "Marmaray Sirkeci",
    "İstanbul",
]
MARMARAY_ANATOLIA_KEYWORDS = [
    "Gebze",
    "Pendik",
    "Söğütlüçeşme",
    "Tuzla",
    "Kartal",
    "Maltepe",
    "Küçükyalı",
    "Ayrılıkçeşmesi",
    "Marmaray Üsküdar",
]

# --- Ramadan footer (imsak / iftar) ---
SHOW_RAMADAN_PANEL = True
RAMADAN_CITY = "Istanbul"
RAMADAN_COUNTRY = "Turkey"
RAMADAN_METHOD = 13  # Diyanet (experimental) in Aladhan API
RAMADAN_TARGET_DATE = "2026-02-20"  # YYYY-MM-DD; empty => today
RAMADAN_API_BASE_URL = "https://api.aladhan.com/v1/timingsByCity"
RAMADAN_TIMEOUT_SECONDS = 15

# If True, allow fallback to the nearest calendar date when today has no service.
ALLOW_CALENDAR_FALLBACK = True
CALENDAR_FALLBACK_DAYS = 500  # Keep minutes visible even when source calendar is old.
SHOW_STATUS_NOTE = False  # Hide fallback/expired notes on board.

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
