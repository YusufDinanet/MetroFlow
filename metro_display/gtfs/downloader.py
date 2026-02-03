"""GTFS download and CKAN resolution."""
import json
import ssl
import time
import urllib.request
from urllib.error import URLError
from pathlib import Path
from typing import Any, Tuple

from .. import config
from .importer import REQUIRED_FILES, OPTIONAL_FILES

try:
    import certifi  # type: ignore
except Exception:  # noqa: BLE001
    certifi = None

if certifi:
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
else:
    SSL_CONTEXT = None


def _urlopen(url: str, timeout: int):
    if SSL_CONTEXT is not None:
        return urllib.request.urlopen(url, timeout=timeout, context=SSL_CONTEXT)
    return urllib.request.urlopen(url, timeout=timeout)


def _fetch_json(url: str) -> dict:
    with _urlopen(url, timeout=20) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def _extract_dataset_slug(url: str) -> str:
    marker = "/dataset/"
    if marker not in url:
        return ""
    part = url.split(marker, 1)[1]
    return part.split("?", 1)[0].split("#", 1)[0].strip("/")


def _resolve_ckan_resources(base_url: str, dataset_id: str) -> dict:
    api = f"{base_url}/package_show?id={dataset_id}"
    data = _fetch_json(api)
    if not data.get("success"):
        return {}
    resources = data["result"].get("resources", [])
    return {r.get("name", ""): r for r in resources}


def _find_resource_url(resources: dict, filename: str) -> str:
    target = filename.replace(".txt", "").replace("_", "").lower()
    for res in resources.values():
        name = (res.get("name") or "").replace(".txt", "").replace("_", "").lower()
        url = res.get("url", "")
        if name == target or target in url.lower():
            return url
    return ""


def resolve_gtfs_source() -> Tuple[str, Any]:
    if config.GTFS_ZIP_URL:
        return "zip", config.GTFS_ZIP_URL

    ckan_url = f"{config.CKAN_BASE_URL}/package_show?id={config.CKAN_DATASET_ID}"
    data = _fetch_json(ckan_url)
    if not data.get("success"):
        raise RuntimeError("CKAN package_show failed")

    resources = data["result"].get("resources", [])
    zip_candidates = []
    for res in resources:
        url = res.get("url", "")
        fmt = (res.get("format") or "").lower()
        if fmt == "zip" or url.lower().endswith(".zip"):
            zip_candidates.append(url)

    if zip_candidates:
        return "zip", zip_candidates[0]

    # Fallback: try to resolve a secondary CKAN dataset (e.g. data.ibb.gov.tr)
    dataset_urls = [r.get("url", "") for r in resources if r.get("url")]
    for url in dataset_urls:
        slug = _extract_dataset_slug(url)
        if not slug:
            continue
        if "data.ibb.gov.tr" not in url:
            continue
        secondary = _resolve_ckan_resources("https://data.ibb.gov.tr/api/3/action", slug)
        if not secondary:
            continue
        mapping = {}
        for filename in REQUIRED_FILES | OPTIONAL_FILES:
            res_url = _find_resource_url(secondary, filename)
            if res_url:
                mapping[filename] = res_url
        if REQUIRED_FILES.issubset(set(mapping.keys())):
            return "csv", mapping

    urls = [r.get("url", "") for r in resources]
    raise RuntimeError(f"No GTFS zip found in CKAN resources: {urls}")


def _is_fresh(path: Path, max_hours: int) -> bool:
    if not path.exists():
        return False
    age = time.time() - path.stat().st_mtime
    return age < max_hours * 3600


def download_gtfs_zip(dest_path: Path) -> Path:
    mode, source = resolve_gtfs_source()
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest_path.with_suffix(".tmp")

    attempts = 3
    last_err = None
    for attempt in range(attempts):
        try:
            if mode == "zip":
                url = str(source)
                with _urlopen(url, timeout=60) as resp, open(tmp_path, "wb") as f:
                    while True:
                        chunk = resp.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
            elif mode == "csv":
                import zipfile

                mapping = source  # type: ignore
                with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                    for filename, url in mapping.items():
                        with _urlopen(url, timeout=60) as resp:
                            zf.writestr(filename, resp.read())
            else:
                raise RuntimeError("Unsupported GTFS source mode")
            last_err = None
            break
        except (URLError, OSError) as err:
            last_err = err
            time.sleep(1 + attempt)

    if last_err is not None:
        raise last_err

    tmp_path.replace(dest_path)
    return dest_path


def ensure_gtfs_zip(dest_path: Path) -> Path:
    if _is_fresh(dest_path, config.GTFS_CACHE_HOURS):
        return dest_path
    try:
        return download_gtfs_zip(dest_path)
    except Exception:
        if dest_path.exists():
            return dest_path
        raise
