"""Terminal output mode for metro display."""
import shutil
import time

from . import app, config
from .db import get_connection


def _format_time(dt) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _clear():
    print("\x1b[2J\x1b[H", end="")


def _terminal_width() -> int:
    if config.TERMINAL_WIDTH and config.TERMINAL_WIDTH > 0:
        return max(config.TERMINAL_WIDTH, 60)
    cols = shutil.get_terminal_size((100, 24)).columns
    return max(min(cols, 120), 60)


def _trim(text: str, max_len: int) -> str:
    if max_len <= 0:
        return ""
    if len(text) <= max_len:
        return text
    if max_len <= 3:
        return text[:max_len]
    return text[: max_len - 3] + "..."


def _frame_row(text: str, width: int) -> str:
    inner = width - 4
    content = _trim(text, inner)
    return f"| {content:<{inner}} |"


def _frame_center(text: str, width: int) -> str:
    inner = width - 2
    content = _trim(text, inner)
    return f"|{content:^{inner}}|"


def _print_model(model) -> None:
    width = _terminal_width()
    inner = width - 2
    separator = "+" + "=" * inner + "+"
    section_separator = "|" + "-" * inner + "|"

    _clear()
    print(separator)
    print(_frame_center(model.title, width))
    print(separator)
    print(_frame_row(f"Updated: {_format_time(model.updated_at)} | Refresh: {config.REFRESH_SECONDS}s", width))
    if model.note:
        print(_frame_row(model.note, width))
    print(section_separator)

    for idx, line in enumerate(model.lines):
        section_title = f" {line.name} "
        print(f"|{section_title:-^{inner}}|")
        for direction in line.directions:
            departures = " | ".join(direction.departures) if direction.departures else "--"
            label = f"{direction.label:<{config.TERMINAL_LABEL_WIDTH}}"
            print(_frame_row(f"{label} {departures}", width))
        if idx < len(model.lines) - 1:
            print(section_separator)

    if model.footer_lines:
        print(section_separator)
        for footer_line in model.footer_lines:
            print(_frame_row(footer_line, width))
    print(separator)


def main() -> None:
    app._ensure_db()
    while True:
        with get_connection() as conn:
            model = app._build_model(conn)
        _print_model(model)
        time.sleep(config.REFRESH_SECONDS)


if __name__ == "__main__":
    main()
