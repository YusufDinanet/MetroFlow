# Metro Flow

## 🚀 Proje Hakkında
Ayrılık Çeşmesi gibi kritik aktarma noktalarında kullanılmak üzere geliştirilmiş gerçek zamanlı bir ulaşım panosudur.  
Python tabanlıdır ve M4 / Marmaray canlı kaynaklarını kullanır; canlı veri alınamazsa GTFS fallback ile çalışmayı sürdürür.

## Özellikler
- M4 ve Marmaray için yaklaşan sefer süreleri
- 1024x600 kiosk odaklı desktop ekran (`metro_flow.desktop`)
- Terminal görünümü (`metro_flow.terminal`)
- PNG/E-Ink render modu (`metro_flow.app`)
- Ramazan alt barı (imsak / iftar + kalan süre)

## 🛠️ Özelleştirme (M3 veya Başka Duraklar İçin)

### 1) Durak Seçimi (`station_id` / `stop_id`)
Ana ayarlar `metro_flow/config.py` dosyasındadır.

- Genel durak adı: `STATION_NAME`
- Hat bazlı sabit duraklar: `LINES[*].stop_ids`
- Hat filtreleri: `LINES[*].route_keywords`, `LINES[*].directions[*].headsign_keywords`

Örnek (M3 gibi başka bir hat eklemek için):

```python
LINES = [
    {
        "name": "M3",
        "route_keywords": ["M3"],
        "stop_ids": ["BURAYA_STOP_ID"],
        "directions": [
            {"label": "Kirazli", "headsign_keywords": ["Kirazli"]},
            {"label": "Basin Ekspres", "headsign_keywords": ["Basin"]},
        ],
    },
]
```

Yerel GTFS veritabanından `stop_id` bulma örneği:

```bash
sqlite3 metro_flow/data/gtfs.sqlite3 "SELECT stop_id, stop_name FROM stops WHERE lower(stop_name) LIKE '%kirazli%';"
```

### 2) API Kaynağı
Proje şu kaynakları kullanır:

- M4 canlı: `https://www.metro.istanbul/SeferDurumlari/SeferDetaylari` ve `https://www.metro.istanbul/SeferDurumlari/AJAXSeferGetir`
- Marmaray canlı: `https://www.tcddtasimacilik.gov.tr/marmaray/tr/gunluk_tren_saatleri` ve `https://api.tcddtasimacilik.gov.tr/api/SubPages/GetTransportationTrainsGroupwithHours?marmaray=true`
- GTFS fallback: `CKAN_BASE_URL` + `CKAN_DATASET_ID` (varsayılan: B40/İBB GTFS)
- Ramazan: `https://api.aladhan.com/v1/timingsByCity`

Farklı hatlara uyarlarken önce ilgili canlı endpoint var mı kontrol et; yoksa GTFS ile çalıştır.

## GTFS Teknik Notu
GTFS (General Transit Feed Specification), toplu taşıma verilerinin (duraklar, güzergahlar, saatler) ortak bir formatta paylaşılmasını sağlayan küresel bir standarttır ve Google tarafından başlatılmıştır.  
Bu projede GTFS verisini canlı kaynaklarla birlikte kullanarak statik tarife + anlık veri yaklaşımı kurulmuştur. Bu yapı, büyük ulaşım veri setlerini gerçek zamanlı işleme tarafında güçlü bir temel sağlar.

### Diğer Hatlara Uyarlama
Bu proje GTFS standartlarını kullandığı için, `config.py` içindeki durak (`Station/Stop ID`) ve hat bilgilerini değiştirerek projeyi herhangi bir İstanbul metrosuna veya Marmaray durağına kısa sürede uyarlayabilirsiniz.

## 📦 Kurulum ve Çalıştırma

### Gereksinimler
- Python `3.11+`
- `tkinter` (pip paketi değildir)

Linux / Raspberry Pi:

```bash
sudo apt update
sudo apt install -y python3-full python3-venv python3-tk
```

### Sanal Ortam

```bash
cd <project_root>
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r metro_flow/requirements.txt
```

### Çalıştırma

Desktop (önerilen):

```bash
python -m metro_flow.desktop
```

Terminal:

```bash
python -m metro_flow.terminal
```

PNG/E-Ink:

```bash
python -m metro_flow.app
```

## Raspberry Pi Kiosk Modu

### Manuel kiosk açılış

```bash
cd /home/<user>/Desktop/<project_root>
source .venv/bin/activate
export DISPLAY=:0
export XAUTHORITY=/home/<user>/.Xauthority
PYTHONPATH="$PWD" python -m metro_flow.desktop
```

Desktop modu kiosk davranışı içerir:
- Tam ekran + başlıksız pencere
- Fare gizleme
- `Esc`: fullscreen çıkış
- `q`: uygulamayı kapatma

### Autostart (systemd)
Repo içinde örnek service: `metro_flow/systemd/metro-flow.service`

1. Servisi sisteme kopyala:

```bash
sudo cp metro_flow/systemd/metro-flow.service /etc/systemd/system/metro-flow.service
```

2. Servis dosyasında `User`, `WorkingDirectory`, `ExecStart` yollarını kendi ortama göre güncelle.

Örnek kiosk servis:

```ini
[Unit]
Description=Metro Flow Desktop
After=graphical.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=yusuf
WorkingDirectory=/home/<user>/Desktop/<project_root>
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/<user>/.Xauthority
Environment=PYTHONPATH=/home/<user>/Desktop/<project_root>
ExecStart=/home/<user>/Desktop/<project_root>/.venv/bin/python -m metro_flow.desktop
Restart=always
RestartSec=5

[Install]
WantedBy=graphical.target
```

3. Etkinleştir:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now metro-flow.service
sudo systemctl status metro-flow.service
```

Log takibi:

```bash
journalctl -u metro-flow.service -f
```

## Konfigürasyon Özeti
Tüm ayarlar: `metro_flow/config.py`

- Genel: `STATION_NAME`, `TIMEZONE`, `REFRESH_SECONDS`
- Canlı/Fallback: `USE_LIVE_SOURCES`, `LIVE_FALLBACK_TO_GTFS`, `SHOW_STATUS_NOTE`
- Hatlar: `LINES`, `stop_ids`, `route_keywords`, `headsign_keywords`
- Desktop: `DESKTOP_WIDTH`, `DESKTOP_HEIGHT`, `DESKTOP_FULLSCREEN`
- Ramazan: `SHOW_RAMADAN_PANEL`, `RAMADAN_TARGET_DATE`

## Sorun Giderme

`No module named metro_flow.desktop`:

```bash
cd /home/<user>/Desktop/<project_root>
PYTHONPATH="$PWD" .venv/bin/python -c "import metro_flow.desktop; print('ok')"
```

`_tkinter` hatası:

```bash
sudo apt install -y python3-tk
```

## Proje Yapısı
- `metro_flow/app.py`: model üretimi ve ana döngü
- `metro_flow/live_sources.py`: canlı kaynak toplayıcı
- `metro_flow/ramadan.py`: imsak/iftar verisi
- `metro_flow/desktop.py`: 1024x600 dashboard/kiosk UI
- `metro_flow/terminal.py`: terminal UI
- `metro_flow/gtfs/`: GTFS indirme/import
- `metro_flow/render/`: PNG/E-Ink render
