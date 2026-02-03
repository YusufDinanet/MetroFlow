"""Layout constants for the e-ink screen."""
from dataclasses import dataclass

from .. import config


@dataclass(frozen=True)
class Layout:
    width: int = config.SCREEN_WIDTH
    height: int = config.SCREEN_HEIGHT
    margin_x: int = 24
    margin_y: int = 20
    section_gap: int = 18
    line_gap: int = 10
    row_gap: int = 6
    label_col_width: int = 220
    value_col_width: int = 520


LAYOUT = Layout()
