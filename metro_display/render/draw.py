"""Render the info screen to a Pillow image."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from PIL import Image, ImageDraw, ImageFont

from .. import config
from .layout import LAYOUT


@dataclass
class DirectionRow:
    label: str
    departures: List[str]


@dataclass
class LineBlock:
    name: str
    directions: List[DirectionRow]


@dataclass
class ScreenModel:
    title: str
    updated_at: datetime
    lines: List[LineBlock]
    note: Optional[str] = None
    footer_lines: List[str] = field(default_factory=list)


def _load_font(size: int) -> ImageFont.ImageFont:
    if config.FONT_PATH:
        try:
            return ImageFont.truetype(config.FONT_PATH, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _safe_draw_text(draw: ImageDraw.ImageDraw, xy, text: str, font: ImageFont.ImageFont, fill: int) -> None:
    try:
        draw.text(xy, text, font=font, fill=fill)
    except UnicodeEncodeError:
        ascii_text = text.encode("ascii", "replace").decode("ascii")
        draw.text(xy, ascii_text, font=font, fill=fill)


def render_screen(model: ScreenModel) -> Image.Image:
    img = Image.new("1", (config.SCREEN_WIDTH, config.SCREEN_HEIGHT), config.BACKGROUND_COLOR)
    draw = ImageDraw.Draw(img)

    font_title = _load_font(config.FONT_TITLE_SIZE)
    font_section = _load_font(config.FONT_SECTION_SIZE)
    font_row = _load_font(config.FONT_ROW_SIZE)
    font_time = _load_font(config.FONT_TIME_SIZE)

    x = LAYOUT.margin_x
    y = LAYOUT.margin_y

    _safe_draw_text(draw, (x, y), model.title, font=font_title, fill=config.FOREGROUND_COLOR)
    y += config.FONT_TITLE_SIZE + LAYOUT.section_gap

    for line in model.lines:
        _safe_draw_text(draw, (x, y), line.name, font=font_section, fill=config.FOREGROUND_COLOR)
        y += config.FONT_SECTION_SIZE + LAYOUT.row_gap

        for direction in line.directions:
            label = f"-> {direction.label}"
            _safe_draw_text(draw, (x, y), label, font=font_row, fill=config.FOREGROUND_COLOR)

            departures = " | ".join(direction.departures) if direction.departures else "--"
            _safe_draw_text(
                draw,
                (x + LAYOUT.label_col_width, y),
                departures,
                font=font_row,
                fill=config.FOREGROUND_COLOR,
            )
            y += config.FONT_ROW_SIZE + LAYOUT.row_gap

        y += LAYOUT.section_gap

    footer_lines = list(model.footer_lines)
    if model.note:
        footer_lines.insert(0, model.note)
    if footer_lines:
        line_height = config.FONT_TIME_SIZE + 4
        start_y = config.SCREEN_HEIGHT - 8 - (line_height * len(footer_lines))
        for idx, line in enumerate(footer_lines):
            _safe_draw_text(draw, (x, start_y + idx * line_height), line, font=font_time, fill=config.FOREGROUND_COLOR)

    return img
