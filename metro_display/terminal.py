"""Terminal output mode for metro display."""
import time

from . import app, config
from .db import get_connection


def _format_time(dt) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _clear():
    print("\x1b[2J\x1b[H", end="")


def _print_model(model) -> None:
    _clear()
    print(model.title)
    print(f"Updated: {_format_time(model.updated_at)} | Refresh: {config.REFRESH_SECONDS}s")
    if model.note:
        print(model.note)
    print("-")
    for line in model.lines:
        print(line.name)
        for direction in line.directions:
            departures = " | ".join(direction.departures) if direction.departures else "--"
            print(f"-> {direction.label:<10} {departures}")
        print("")


def main() -> None:
    app._ensure_db()
    while True:
        with get_connection() as conn:
            model = app._build_model(conn)
        _print_model(model)
        time.sleep(config.REFRESH_SECONDS)


if __name__ == "__main__":
    main()
