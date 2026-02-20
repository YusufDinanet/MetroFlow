"""Desktop dashboard UI (1024x600) with station-sign look."""
import re
import threading
from datetime import datetime
from typing import Dict, List, Optional, Tuple

try:
    import tkinter as tk
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(
        "tkinter bulunamadi. macOS (Homebrew Python) icin once su komutu calistir:\n"
        "  brew install python-tk@3.11\n"
        "Sonra proje icinde .venv ile calistir:\n"
        "  source .venv/bin/activate\n"
        "  python -m metro_flow.desktop"
    ) from exc

from . import app, config
from .db import get_connection
from .render.draw import LineBlock, ScreenModel

BG_TOP = "#1d2533"
BG_BOTTOM = "#0b1220"
SHELL_OUTER = "#090d15"
SHELL_INNER = "#121a28"
PANEL_FILL = "#182235"
PANEL_BORDER = "#43516c"
PANEL_DIVIDER = "#2c3850"

TEXT_MAIN = "#f7fbff"
TEXT_MUTED = "#aab6cb"
TEXT_SOFT = "#7f8aa2"
CYAN = "#3fe2ff"
MAGENTA = "#ff5de2"
GREEN = "#66ffac"

RAM_BG = "#122013"
RAM_BORDER = "#2f6c46"
RAM_TITLE = "#def9e5"
RAM_TEXT = "#f0fff3"
RAM_ACCENT = "#ffd35a"


def _safe_text(value: str) -> str:
    return value or ""


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _trim_text(text: str, max_len: int) -> str:
    if max_len <= 0:
        return ""
    if len(text) <= max_len:
        return text
    if max_len <= 3:
        return text[:max_len]
    return text[: max_len - 3] + "..."


def _fit_font_for_width(text: str, max_px: int, preferred: int, minimum: int) -> int:
    if max_px <= 0:
        return minimum
    chars = max(1, len(text or ""))
    # Approximate width factor for bold digital glyphs in Tk.
    width_bound = int(max_px / (chars * 0.62))
    return _clamp(min(preferred, width_bound), minimum, preferred)


def _hex_to_rgb(value: str) -> Tuple[int, int, int]:
    raw = value.lstrip("#")
    if len(raw) != 6:
        return (0, 0, 0)
    return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))


def _rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _blend_color(a: str, b: str, t: float) -> str:
    t = max(0.0, min(1.0, t))
    ar, ag, ab = _hex_to_rgb(a)
    br, bg, bb = _hex_to_rgb(b)
    return _rgb_to_hex(
        (
            int(ar + (br - ar) * t),
            int(ag + (bg - ag) * t),
            int(ab + (bb - ab) * t),
        )
    )


def _parse_departure(dep: str) -> Dict[str, object]:
    dep = (dep or "").strip()
    out: Dict[str, object] = {
        "minutes": None,
        "time": "",
        "next_day": False,
    }
    if not dep or dep == "--":
        return out

    if dep.lower().startswith("yarın"):
        match = re.search(r"(\d{2}:\d{2})", dep)
        out["minutes"] = 24 * 60
        out["time"] = match.group(1) if match else ""
        out["next_day"] = True
        return out

    match = re.match(r"^\s*(\d+)\s+dk\s+(\d{2}:\d{2})\s*$", dep, re.I)
    if match:
        out["minutes"] = int(match.group(1))
        out["time"] = match.group(2)
        return out

    match = re.search(r"(\d{2}:\d{2})", dep)
    if match:
        out["time"] = match.group(1)
    return out


def _departure_label(dep: str) -> str:
    info = _parse_departure(dep)
    minutes = info["minutes"]
    time_str = str(info["time"] or "")
    next_day = bool(info["next_day"])

    if next_day:
        if time_str:
            return time_str
        return "--"
    if minutes is None:
        return "--"

    threshold = getattr(config, "DESKTOP_SHOW_TIME_AFTER_MINUTES", 30)
    if int(minutes) > int(threshold) and time_str:
        return time_str
    return str(int(minutes))


def _line_theme(line_name: str) -> Tuple[str, str]:
    norm = line_name.lower()
    if "marmaray" in norm:
        return (CYAN, CYAN)
    if norm == "m4" or "m4" in norm:
        return (MAGENTA, MAGENTA)
    return ("#7edfff", "#f5cf58")


def _line_title(line_name: str) -> str:
    norm = line_name.lower()
    if "marmaray" in norm:
        return "MARMARAY 🚉"
    if norm == "m4" or "m4" in norm:
        return "M4 METRO LINE 🚇"
    return f"{line_name.upper()} 🚇"


def _line_rows(line: LineBlock) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for direction in line.directions:
        raw_deps = direction.departures if direction.departures else ["--"]
        dep_infos = [_parse_departure(dep) for dep in raw_deps[:2]]
        cells = [_departure_label(dep) for dep in raw_deps[:2]]
        next_day_flags = [bool(info.get("next_day")) for info in dep_infos]
        while len(cells) < 2:
            cells.append("--")
            next_day_flags.append(False)

        first = _parse_departure(raw_deps[0]) if raw_deps else _parse_departure("--")
        rows.append(
            {
                "dest": _safe_text(direction.label),
                "cells": cells,
                "next_day_flags": next_day_flags,
                "first_minutes": first["minutes"],
                "first_next_day": first["next_day"],
            }
        )
    return rows


def _minute_color(label: str, minute_base: str, is_next_day: bool = False) -> str:
    if is_next_day:
        return CYAN
    if label == "--":
        return TEXT_SOFT
    if re.fullmatch(r"\d{2}:\d{2}", label):
        return TEXT_MUTED
    try:
        minute = int(label)
    except ValueError:
        return TEXT_MAIN
    if minute == 0:
        return GREEN
    if minute <= 2:
        return GREEN
    return minute_base


def _eta_display_text(label: str) -> str:
    if label == "--":
        return "--"
    if label.isdigit():
        return f"{int(label)} dk"
    return label


def _row_indicator_color(row: Dict[str, object], accent: str) -> str:
    if bool(row.get("first_next_day")):
        return CYAN
    minutes = row.get("first_minutes")
    if minutes is None:
        return TEXT_SOFT
    try:
        minute = int(minutes)
    except Exception:  # noqa: BLE001
        return TEXT_SOFT
    if minute <= 2:
        return GREEN
    if minute <= 10:
        return accent
    if minute <= int(getattr(config, "DESKTOP_SHOW_TIME_AFTER_MINUTES", 30)):
        return _blend_color(accent, TEXT_MAIN, 0.35)
    return TEXT_SOFT


def _parse_ramadan(footer_lines: List[str]) -> Dict[str, str]:
    out = {
        "title": "Ramazan - Istanbul",
        "imsak_time": "--:--",
        "imsak_left": "--",
        "iftar_time": "--:--",
        "iftar_left": "--",
    }
    if footer_lines:
        out["title"] = footer_lines[0]
    if len(footer_lines) >= 2:
        match = re.search(
            r"Imsak\s+(\d{2}:\d{2})\s+\(([^)]+)\)\s+\|\s+Iftar\s+(\d{2}:\d{2})\s+\(([^)]+)\)",
            footer_lines[1],
            re.I,
        )
        if match:
            out["imsak_time"] = match.group(1)
            out["imsak_left"] = match.group(2)
            out["iftar_time"] = match.group(3)
            out["iftar_left"] = match.group(4)
    return out


class DesktopBoard:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Metro Flow")
        self.root.configure(bg=config.DESKTOP_BG_COLOR)
        self.root.geometry(f"{config.DESKTOP_WIDTH}x{config.DESKTOP_HEIGHT}")
        self.root.minsize(min(640, config.DESKTOP_WIDTH), min(360, config.DESKTOP_HEIGHT))
        self._is_fullscreen = False
        self._is_kiosk = False
        self.root.bind("<Escape>", self._exit_fullscreen)
        self.root.bind("q", lambda _e: self.root.destroy())
        self.root.bind("<F11>", self._toggle_fullscreen)
        self.root.bind("<FocusIn>", self._on_focus_in)
        self.root.bind("<FocusOut>", self._on_focus_out)

        self.canvas = tk.Canvas(
            self.root,
            bg=config.DESKTOP_BG_COLOR,
            highlightthickness=0,
            bd=0,
            cursor="none",
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", self._on_resize)

        self.model = ScreenModel(
            title=config.STATION_NAME.upper(),
            updated_at=datetime.now(),
            lines=[],
            note="Yukleniyor...",
            footer_lines=[],
        )
        self._refresh_inflight = False
        if config.DESKTOP_FULLSCREEN:
            self._enter_fullscreen(kiosk=True)
        self._apply_cursor(hidden=True)

    def _apply_cursor(self, hidden: bool):
        cursor = "none" if hidden else ""
        try:
            self.root.configure(cursor=cursor)
        except tk.TclError:
            pass
        try:
            self.canvas.configure(cursor=cursor)
        except tk.TclError:
            pass

    def _enter_fullscreen(self, kiosk: bool = True):
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.root.geometry(f"{screen_w}x{screen_h}+0+0")
        try:
            self.root.attributes("-fullscreen", True)
        except tk.TclError:
            pass
        if kiosk:
            try:
                self.root.overrideredirect(True)
            except tk.TclError:
                pass
        self._is_fullscreen = True
        self._is_kiosk = kiosk
        self._apply_cursor(hidden=True)

    def _exit_fullscreen(self, _event=None):
        if not self._is_fullscreen:
            return "break"
        try:
            self.root.overrideredirect(False)
        except tk.TclError:
            pass
        try:
            self.root.attributes("-fullscreen", False)
        except tk.TclError:
            pass
        self.root.geometry(f"{config.DESKTOP_WIDTH}x{config.DESKTOP_HEIGHT}+40+40")
        self._is_fullscreen = False
        self._is_kiosk = False
        self._apply_cursor(hidden=False)
        return "break"

    def _toggle_fullscreen(self, _event=None):
        if self._is_fullscreen:
            return self._exit_fullscreen()
        self._enter_fullscreen(kiosk=True)
        return "break"

    def _on_focus_in(self, _event=None):
        self._apply_cursor(hidden=True)

    def _on_focus_out(self, _event=None):
        if self._is_fullscreen:
            return
        self._apply_cursor(hidden=False)

    def _font(self, size: int, weight: str = "normal"):
        return (config.DESKTOP_FONT_FAMILY, size, weight)

    def _on_resize(self, _event):
        self._draw()

    def _draw_background(self, width: int, height: int):
        for y in range(height):
            color = _blend_color(BG_TOP, BG_BOTTOM, y / float(max(1, height - 1)))
            self.canvas.create_line(0, y, width, y, fill=color)

    def _draw_shell(self, width: int, height: int) -> Tuple[int, int, int, int]:
        margin = _clamp(int(min(width, height) * 0.022), 10, 24)
        self.canvas.create_rectangle(
            margin,
            margin,
            width - margin,
            height - margin,
            fill=SHELL_OUTER,
            outline="#2f3b50",
            width=2,
        )

        inset = margin + _clamp(int(min(width, height) * 0.012), 6, 10)
        self.canvas.create_rectangle(
            inset,
            inset,
            width - inset,
            height - inset,
            fill=SHELL_INNER,
            outline="#445577",
            width=1,
        )
        return (inset + 10, inset + 8, width - inset - 10, height - inset - 8)

    def _draw_header(self, x0: int, y0: int, x1: int) -> int:
        width = x1 - x0
        station_font = _clamp(int(width * 0.012), 10, 15)
        clock_font = _clamp(int(width * 0.038), 22, 40)
        self.canvas.create_text(
            x0 + 8,
            y0 + 26,
            anchor="w",
            text=self.model.title,
            fill=TEXT_SOFT,
            font=self._font(station_font, "bold"),
        )
        clock = self.model.updated_at.strftime("%H:%M")
        self.canvas.create_text(
            x1 - 6,
            y0 + 30,
            anchor="e",
            text=clock,
            fill="#0f1118",
            font=self._font(clock_font, "bold"),
        )
        self.canvas.create_text(
            x1 - 8,
            y0 + 28,
            anchor="e",
            text=clock,
            fill=TEXT_MAIN,
            font=self._font(clock_font, "bold"),
        )
        return y0 + _clamp(int(clock_font * 1.22), 48, 62)

    def _draw_line_panel(self, x0: int, y0: int, x1: int, h: int, line: LineBlock):
        accent, minute_base = _line_theme(line.name)
        rows = _line_rows(line)[:2]
        if not rows:
            rows = [
                {"dest": "--", "cells": ["--", "--"], "next_day_flags": [False, False], "first_minutes": None, "first_next_day": False},
                {"dest": "--", "cells": ["--", "--"], "next_day_flags": [False, False], "first_minutes": None, "first_next_day": False},
            ]
        panel_w = x1 - x0
        y1 = y0 + h

        self.canvas.create_rectangle(x0, y0, x1, y1, fill=PANEL_FILL, outline=PANEL_BORDER, width=1)

        if panel_w < 700:
            left_ratio = 0.52
        elif panel_w < 820:
            left_ratio = 0.55
        elif panel_w < 980:
            left_ratio = 0.59
        else:
            left_ratio = 0.62
        left_w = int(panel_w * left_ratio)
        left_x1 = x0 + left_w

        header_h = _clamp(int(h * 0.30), 48, 70)
        title_font = _clamp(int(header_h * 0.46), 18, 30)
        header_meta_font = _clamp(int(header_h * 0.22), 9, 14)

        self.canvas.create_text(
            x0 + 18,
            y0 + int(header_h * 0.38),
            anchor="w",
            text=_trim_text(_line_title(line.name), 22 if panel_w > 850 else 18),
            fill=TEXT_MAIN,
            font=self._font(title_font, "bold"),
        )

        self.canvas.create_text(
            x0 + 20,
            y0 + header_h - 12,
            anchor="w",
            text="DESTINATION",
            fill=TEXT_MUTED,
            font=self._font(header_meta_font, "bold"),
        )
        self.canvas.create_line(x0 + 16, y0 + header_h, left_x1 - 16, y0 + header_h, fill=PANEL_DIVIDER, width=1)
        self.canvas.create_line(left_x1, y0 + 14, left_x1, y1 - 14, fill=PANEL_DIVIDER, width=1)

        right_w = panel_w - left_w
        right_x0 = left_x1
        use_two_columns = right_w >= 300
        eta_header = "MINUTES AWAY" if use_two_columns else "ETA"
        self.canvas.create_text(
            right_x0 + right_w / 2,
            y0 + header_h - 12,
            anchor="center",
            text=eta_header,
            fill=minute_base,
            font=self._font(header_meta_font, "bold"),
        )
        self.canvas.create_line(right_x0 + 16, y0 + header_h, x1 - 16, y0 + header_h, fill=PANEL_DIVIDER, width=1)

        row_top = y0 + header_h + 10
        row_bottom = y1 - 10
        count = max(1, len(rows))
        row_step = (row_bottom - row_top) / float(count)

        dest_font = _clamp(int(row_step * 0.37), 13, 24)
        minute_pref = _clamp(int(row_step * 0.40), 14, 26)
        time_pref = _clamp(minute_pref - 3, 12, 22)
        indicator_outer = _clamp(int(row_step * 0.13), 6, 10)
        indicator_inner = _clamp(indicator_outer - 3, 2, 5)

        col1 = int(right_x0 + right_w * 0.33)
        col2 = int(right_x0 + right_w * 0.75)

        for idx, row in enumerate(rows):
            y_mid = int(row_top + idx * row_step + row_step * 0.5)
            dest = str(row["dest"])
            dest_color = accent if idx == 0 else TEXT_MAIN

            indicator = _row_indicator_color(row, accent)
            self.canvas.create_oval(
                x0 + 18,
                y_mid - indicator_outer,
                x0 + 18 + indicator_outer * 2,
                y_mid + indicator_outer,
                outline=indicator,
                fill="",
                width=1,
            )
            self.canvas.create_oval(
                x0 + 18 + (indicator_outer - indicator_inner),
                y_mid - indicator_inner,
                x0 + 18 + (indicator_outer - indicator_inner) + indicator_inner * 2,
                y_mid + indicator_inner,
                outline="",
                fill=indicator,
            )

            left_text_px = max(90, left_w - (34 + indicator_outer * 2) - 22)
            dest_char_budget = max(8, int(left_text_px / max(7.0, dest_font * 0.53)))
            self.canvas.create_text(
                x0 + 26 + indicator_outer * 2,
                y_mid,
                anchor="w",
                text=_trim_text(dest, dest_char_budget),
                fill=dest_color,
                font=self._font(dest_font, "normal"),
            )

            mins: List[str] = row["cells"]  # type: ignore[assignment]
            next_day_flags: List[bool] = row.get("next_day_flags", [False, False])  # type: ignore[assignment]
            m1 = mins[0] if len(mins) > 0 else "--"
            m2 = mins[1] if len(mins) > 1 else "--"
            f1 = bool(next_day_flags[0]) if len(next_day_flags) > 0 else False
            f2 = bool(next_day_flags[1]) if len(next_day_flags) > 1 else False
            eta1 = _eta_display_text(m1)
            eta2 = _eta_display_text(m2)
            if use_two_columns:
                col_max_px = max(72, int(right_w * 0.34))
                m1_pref = time_pref if ":" in eta1 else minute_pref
                m2_pref = time_pref if ":" in eta2 else minute_pref
                m1_font = _fit_font_for_width(eta1, col_max_px, m1_pref, 11)
                m2_font = _fit_font_for_width(eta2, col_max_px, m2_pref, 11)
                self.canvas.create_text(
                    col1,
                    y_mid,
                    anchor="center",
                    text=eta1,
                    fill=_minute_color(m1, minute_base, f1),
                    font=self._font(m1_font, "bold"),
                )
                self.canvas.create_text(
                    col2,
                    y_mid,
                    anchor="center",
                    text=eta2,
                    fill=_minute_color(m2, minute_base, f2),
                    font=self._font(m2_font, "bold"),
                )
            else:
                combo = eta1 if eta2 == "--" else f"{eta1} | {eta2}"
                combo_pref = minute_pref if ":" not in combo else time_pref
                combo_font = _fit_font_for_width(combo, max(120, int(right_w * 0.8)), combo_pref, 11)
                combo_color = _minute_color(m1, minute_base, f1) if m1 != "--" else _minute_color(m2, minute_base, f2)
                self.canvas.create_text(
                    right_x0 + right_w / 2,
                    y_mid,
                    anchor="center",
                    text=combo,
                    fill=combo_color,
                    font=self._font(combo_font, "bold"),
                )

    def _draw_crescent(self, cx: int, cy: int, radius: int):
        self.canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, fill=RAM_ACCENT, outline="")
        self.canvas.create_oval(
            cx - radius + 8,
            cy - radius - 1,
            cx + radius + 8,
            cy + radius - 1,
            fill=RAM_BG,
            outline="",
        )

    def _draw_ramadan_bar(self, x0: int, y0: int, x1: int, h: int):
        ram = _parse_ramadan(self.model.footer_lines)
        y1 = y0 + h
        bar_w = x1 - x0
        self.canvas.create_rectangle(x0, y0, x1, y1, fill=RAM_BG, outline=RAM_BORDER, width=1)
        self._draw_crescent(x0 + 24, y0 + h // 2, 11)
        if bar_w < 760:
            title_font = _clamp(int(h * 0.24), 10, 16)
            value_font = _clamp(int(h * 0.23), 10, 14)
            self.canvas.create_text(
                x0 + 44,
                y0 + int(h * 0.34),
                anchor="w",
                text=f"🕌 {_trim_text(ram['title'], 34)}",
                fill=RAM_TEXT,
                font=self._font(title_font, "normal"),
            )
            compact = f"Imsak {ram['imsak_time']} ({ram['imsak_left']})   Iftar {ram['iftar_time']} ({ram['iftar_left']})"
            self.canvas.create_text(
                x0 + 44,
                y0 + int(h * 0.72),
                anchor="w",
                text=_trim_text(compact, 68),
                fill=RAM_ACCENT,
                font=self._font(value_font, "bold"),
            )
            return

        title_font = _clamp(int(h * 0.27), 12, 18)
        label_font = _clamp(int(h * 0.20), 10, 14)
        value_font = _clamp(int(h * 0.24), 11, 16)

        self.canvas.create_text(
            x0 + 44,
            y0 + h // 2,
            anchor="w",
            text=f"🕌 {_trim_text(ram['title'], 42)}",
            fill=RAM_TEXT,
            font=self._font(title_font, "normal"),
        )

        info_x = x0 + int(bar_w * 0.50)
        self.canvas.create_text(
            info_x,
            y0 + 18,
            anchor="w",
            text="SAHUR / IMSAK",
            fill=RAM_TITLE,
            font=self._font(label_font, "bold"),
        )
        self.canvas.create_text(
            info_x,
            y0 + h - 20,
            anchor="w",
            text=f"{ram['imsak_time']}  Kalan {ram['imsak_left']}",
            fill=RAM_TEXT,
            font=self._font(value_font, "bold"),
        )

        iftar_x = x0 + int(bar_w * 0.76)
        self.canvas.create_text(
            iftar_x,
            y0 + 18,
            anchor="w",
            text="IFTAR",
            fill=RAM_ACCENT,
            font=self._font(label_font, "bold"),
        )
        self.canvas.create_text(
            iftar_x,
            y0 + h - 20,
            anchor="w",
            text=f"{ram['iftar_time']}  Kalan {ram['iftar_left']}",
            fill=RAM_ACCENT,
            font=self._font(value_font, "bold"),
        )

    def _draw(self):
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        if width < 100 or height < 100:
            return

        self.canvas.delete("all")
        self._draw_background(width, height)
        x0, y0, x1, y1 = self._draw_shell(width, height)

        header_bottom = self._draw_header(x0, y0, x1)
        inner_h = y1 - header_bottom
        show_ramadan = config.SHOW_RAMADAN_PANEL and bool(self.model.footer_lines)
        footer_h = _clamp(int(inner_h * 0.14), 58, 78) if show_ramadan else 0
        cards_gap = _clamp(int(inner_h * 0.022), 8, 14)
        cards_total = max(120, inner_h - footer_h - (cards_gap if show_ramadan else 0))
        card_h = max(90, int((cards_total - cards_gap) / 2))
        panel_w = x1 - x0

        lines = self.model.lines[:2]
        if len(lines) < 2:
            lines = lines + [LineBlock(name="LINE", directions=[])] * (2 - len(lines))

        self._draw_line_panel(x0, header_bottom, x0 + panel_w, card_h, lines[0])
        second_y = header_bottom + card_h + cards_gap
        self._draw_line_panel(x0, second_y, x0 + panel_w, card_h, lines[1])

        if show_ramadan:
            ram_y = y1 - footer_h
            self._draw_ramadan_bar(x0, ram_y, x1, footer_h)

        if self.model.note and getattr(config, "SHOW_STATUS_NOTE", False):
            self.canvas.create_text(
                x1 - 6,
                y1 - 4,
                anchor="se",
                text=self.model.note,
                fill=TEXT_SOFT,
                font=self._font(11, "normal"),
            )

    def _safe_after(self, fn, *args):
        try:
            self.root.after(0, fn, *args)
        except Exception:  # noqa: BLE001
            pass

    def _refresh_model_worker(self):
        try:
            with get_connection() as conn:
                model = app._build_model(conn)
            self._safe_after(self._refresh_success, model)
        except Exception as err:  # noqa: BLE001
            self._safe_after(self._refresh_error, err)
        finally:
            self._safe_after(self._refresh_done)

    def _refresh_success(self, model: ScreenModel):
        self.model = model
        self._draw()

    def _refresh_error(self, err: Exception):
        self.model = ScreenModel(
            title=config.STATION_NAME.upper(),
            updated_at=datetime.now(),
            lines=self.model.lines,
            note=f"Hata: {err}",
            footer_lines=self.model.footer_lines,
        )
        self._draw()

    def _refresh_done(self):
        self._refresh_inflight = False

    def _refresh_tick(self):
        if not self._refresh_inflight:
            self._refresh_inflight = True
            worker = threading.Thread(target=self._refresh_model_worker, daemon=True)
            worker.start()
        self.root.after(max(5, int(config.REFRESH_SECONDS)) * 1000, self._refresh_tick)

    def run(self):
        app._ensure_db()
        self._draw()
        self._refresh_tick()
        self.root.mainloop()


def main() -> None:
    DesktopBoard().run()


if __name__ == "__main__":
    main()
