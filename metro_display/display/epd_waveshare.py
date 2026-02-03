"""Waveshare e-ink driver wrapper.

Requires waveshare_epd package on the Raspberry Pi.
"""
from PIL import Image

from .epd_base import EpdDisplay


class WaveshareEPD(EpdDisplay):
    def __init__(self) -> None:  # pragma: no cover - hardware
        try:
            from waveshare_epd import epd7in5_V2
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "waveshare_epd not installed. Install on the Pi before using DISPLAY_DRIVER=waveshare."
            ) from exc
        self._epd = epd7in5_V2.EPD()
        self._epd.init()

    def display(self, image: Image.Image) -> None:  # pragma: no cover - hardware
        self._epd.display(self._epd.getbuffer(image))
