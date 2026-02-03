"""Resolve routes and stops for a station."""
from typing import Iterable, List

from ..db import query
from ..gtfs.parser import normalize_text, tokenize_text


def resolve_route_ids(conn, keywords: Iterable[str]) -> List[str]:
    rows = query(conn, "SELECT route_id, route_short_name, route_long_name FROM routes")
    if not keywords:
        return [r["route_id"] for r in rows]
    norm_keywords = [normalize_text(k) for k in keywords]
    route_ids = []
    for r in rows:
        hay = normalize_text(f"{r['route_short_name'] or ''} {r['route_long_name'] or ''}")
        if any(k in hay for k in norm_keywords):
            route_ids.append(r["route_id"])
    return route_ids


def _token_match(target_tokens: List[str], name_tokens: List[str]) -> bool:
    if not target_tokens or not name_tokens:
        return False
    for t in target_tokens:
        matched = False
        for n in name_tokens:
            if t == n:
                matched = True
                break
            if len(t) >= 3 and len(n) >= 3 and (t.startswith(n) or n.startswith(t)):
                matched = True
                break
        if not matched:
            return False
    return True


def resolve_stop_ids(conn, stop_name: str, route_ids: List[str]) -> List[str]:
    target = normalize_text(stop_name)
    target_tokens = tokenize_text(stop_name)
    rows = query(conn, "SELECT stop_id, stop_name FROM stops")
    candidates = []
    for r in rows:
        name_norm = normalize_text(r["stop_name"] or "")
        name_tokens = tokenize_text(r["stop_name"] or "")
        if not name_norm:
            continue
        if target in name_norm or name_norm in target or _token_match(target_tokens, name_tokens):
            candidates.append(r["stop_id"])
    if not candidates:
        return []
    if not route_ids:
        return candidates

    placeholders = ",".join(["?"] * len(route_ids))
    stop_placeholders = ",".join(["?"] * len(candidates))
    sql = f"""
        SELECT DISTINCT st.stop_id
        FROM stop_times st
        JOIN trips t ON t.trip_id = st.trip_id
        WHERE t.route_id IN ({placeholders})
          AND st.stop_id IN ({stop_placeholders})
    """
    params = list(route_ids) + list(candidates)
    rows = query(conn, sql, params)
    return [r["stop_id"] for r in rows]
