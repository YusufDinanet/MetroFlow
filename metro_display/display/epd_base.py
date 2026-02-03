"""Display driver base class."""
from PIL import Image


class EpdDisplay:
    def display(self, image: Image.Image) -> None:  # pragma: no cover - hardware
        raise NotImplementedError
