"""GTFS parsing helpers."""
from typing import List, Optional


def gtfs_time_to_seconds(value: str) -> Optional[int]:
    if not value:
        return None
    parts = value.split(":")
    if len(parts) < 2:
        return None
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        return None
    if hours < 0 or minutes < 0 or seconds < 0:
        return None
    return hours * 3600 + minutes * 60 + seconds


def seconds_to_hhmm(seconds: int) -> str:
    if seconds < 0:
        return "--:--"
    hours = (seconds // 3600) % 24
    minutes = (seconds % 3600) // 60
    return f"{hours:02d}:{minutes:02d}"


def normalize_text(text: str) -> str:
    if text is None:
        return ""
    t = text.strip().lower()
    t = (
        t.replace("ı", "i")
        .replace("ğ", "g")
        .replace("ü", "u")
        .replace("ş", "s")
        .replace("ö", "o")
        .replace("ç", "c")
    )
    out = []
    for ch in t:
        if ch.isalnum():
            out.append(ch)
    return "".join(out)


def tokenize_text(text: str) -> List[str]:
    if text is None:
        return []
    t = text.strip().lower()
    t = (
        t.replace("ı", "i")
        .replace("ğ", "g")
        .replace("ü", "u")
        .replace("ş", "s")
        .replace("ö", "o")
        .replace("ç", "c")
    )
    tokens = []
    buf = []
    for ch in t:
        if ch.isalnum():
            buf.append(ch)
        else:
            if buf:
                tokens.append("".join(buf))
                buf.clear()
    if buf:
        tokens.append("".join(buf))
    return tokens
