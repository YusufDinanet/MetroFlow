#!/usr/bin/env node
"use strict";

// Terminal watcher for M4 (Metro Istanbul API / Metro Istanbul web schedule).
// Refreshes every 10s and alerts when arrivals are <= 6 minutes.

const fs = require("fs");
const path = require("path");
const { Readable } = require("stream");
const { TextDecoder } = require("util");

const BASE_URL = (process.env.METRO_API_BASE ||
  "https://api.ibb.gov.tr/MetroIstanbul/api/MetroMobile/V2").replace(/\/$/, "");
const STATION_NAME = process.env.STATION_NAME || "Ayrilikcesmesi";
const LINE_ID = parseInt(process.env.M4_LINE_ID || "3", 10); // M4 line id
const MODE = (process.env.MODE || "metro").toLowerCase(); // metro | auto | live | scheduled
const REFRESH_SEC = parseInt(process.env.REFRESH_SEC || "10", 10);
const ALERT_MINUTES = parseInt(process.env.ALERT_MINUTES || "6", 10);
const SHOW_COUNT = parseInt(process.env.SHOW_COUNT || "3", 10);
const DISPLAY_MAX_MINUTES = parseInt(process.env.DISPLAY_MAX_MINUTES || "10", 10);
const HEADERS_JSON = process.env.METRO_HEADERS_JSON || "";
const STATION_ID_OVERRIDE = parseInt(process.env.STATION_ID || "", 10);
const BEEP = (process.env.BEEP || "1") !== "0";
const DISABLE_DEFAULT_HEADERS = (process.env.DISABLE_DEFAULT_HEADERS || "0") === "1";

const GTFS_DATASET = process.env.GTFS_DATASET || "public-transport-gtfs-data";
const GTFS_CACHE_DIR = process.env.GTFS_CACHE_DIR || ".gtfs-cache";
const GTFS_CACHE_HOURS = parseInt(process.env.GTFS_CACHE_HOURS || "24", 10);
const GTFS_ENCODING = process.env.GTFS_ENCODING || "windows-1254";
const ROUTE_FILTERS = (process.env.ROUTE_FILTERS || "M4")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);

const METRO_WEB_URL = "https://www.metro.istanbul/SeferDurumlari/SeferDetaylari";
const METRO_WEB_AJAX = "https://www.metro.istanbul/SeferDurumlari/AJAXSeferGetir";
const METRO_WEB_LINE_ID = parseInt(process.env.METRO_WEB_LINE_ID || "3", 10); // M4
const METRO_WEB_CACHE_MINUTES = parseInt(process.env.METRO_WEB_CACHE_MINUTES || "60", 10);

const DEFAULT_HEADERS = {
  "User-Agent":
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
  Accept: "application/json, text/plain, */*",
  "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
  Origin: "https://www.metro.istanbul",
  Referer: "https://www.metro.istanbul/",
};

function parseCsvLine(line) {
  const out = [];
  let current = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (ch === "\"") {
      if (inQuotes && line[i + 1] === "\"") {
        current += "\"";
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (ch === "," && !inQuotes) {
      out.push(current);
      current = "";
      continue;
    }
    current += ch;
  }
  out.push(current);
  return out;
}

function decodeHtml(text) {
  return (text || "")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, "\"")
    .replace(/&#39;/g, "'")
    .replace(/&gt;/g, ">")
    .replace(/&lt;/g, "<")
    .replace(/&#(\d+);/g, (_, code) => String.fromCharCode(parseInt(code, 10)));
}

function extractSelectOptions(html, selectId) {
  const selectRe = new RegExp(
    `<select[^>]*id="${selectId}"[^>]*>[\\s\\S]*?<\\/select>`,
    "i"
  );
  const match = html.match(selectRe);
  if (!match) return [];
  const selectHtml = match[0];
  const optionRe = /<option[^>]*value="([^"]*)"[^>]*>([\s\S]*?)<\/option>/gi;
  const options = [];
  let m;
  while ((m = optionRe.exec(selectHtml))) {
    const value = (m[1] || "").trim();
    let text = decodeHtml(m[2] || "").trim();
    if (!value) continue;
    if (!text || normalize(text) === "sec") continue;
    options.push({ value, text });
  }
  return options;
}

function extractKod(html) {
  const m =
    html.match(/formData\\.append\\(\"kod\",\\s*'([^']+)'\\)/i) ||
    html.match(/formData\\.append\\(\"kod\",\\s*\"([^\"]+)\"\\)/i);
  return m ? m[1] : "";
}

function formatRouteLabel(text) {
  return (text || "").replace(/-->>/g, "->").replace(/\s+/g, " ").trim();
}

async function readCsv(filePath, onRow, encoding = "utf-8") {
  const buffer = await fs.promises.readFile(filePath);
  let text;
  try {
    text = new TextDecoder(encoding).decode(buffer);
  } catch (err) {
    text = buffer.toString("utf8");
  }
  const lines = text.split(/\r?\n/);
  let headers = null;
  for (const line of lines) {
    if (!headers) {
      headers = parseCsvLine(line);
      continue;
    }
    if (!line || !line.trim()) continue;
    const values = parseCsvLine(line);
    const row = {};
    for (let i = 0; i < headers.length; i += 1) {
      row[headers[i]] = values[i] !== undefined ? values[i] : "";
    }
    await onRow(row);
  }
}

function dateKey(date) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}`;
}

function formatDateKey(key) {
  if (!key || key.length !== 8) return key || "";
  return `${key.slice(0, 4)}-${key.slice(4, 6)}-${key.slice(6, 8)}`;
}

function parseDateKey(key) {
  if (!key || key.length !== 8) return null;
  const year = parseInt(key.slice(0, 4), 10);
  const month = parseInt(key.slice(4, 6), 10);
  const day = parseInt(key.slice(6, 8), 10);
  if (Number.isNaN(year) || Number.isNaN(month) || Number.isNaN(day)) return null;
  return new Date(year, month - 1, day);
}

function selectServiceDate(now, minStart, maxEnd) {
  const todayKey = dateKey(now);
  if (minStart && maxEnd && todayKey >= minStart && todayKey <= maxEnd) {
    return { date: new Date(now.getFullYear(), now.getMonth(), now.getDate()), key: todayKey, fallback: false };
  }
  if (!minStart || !maxEnd) {
    return { date: new Date(now.getFullYear(), now.getMonth(), now.getDate()), key: todayKey, fallback: false };
  }

  const targetDow = now.getDay();
  let baseKey = todayKey > maxEnd ? maxEnd : minStart;
  let date = parseDateKey(baseKey);
  if (!date) {
    return { date: new Date(now.getFullYear(), now.getMonth(), now.getDate()), key: todayKey, fallback: false };
  }

  for (let i = 0; i < 7; i += 1) {
    if (date.getDay() === targetDow) break;
    date.setDate(date.getDate() + (todayKey > maxEnd ? -1 : 1));
  }

  const key = dateKey(date);
  return {
    date,
    key,
    fallback: true,
    reason: todayKey > maxEnd ? `calendar ends ${formatDateKey(maxEnd)}` : `calendar starts ${formatDateKey(minStart)}`,
  };
}

function parseGtfsTimeToMinutes(value) {
  if (!value) return null;
  const parts = value.split(":");
  if (parts.length < 2) return null;
  const hours = parseInt(parts[0], 10);
  const minutes = parseInt(parts[1], 10);
  const seconds = parts.length > 2 ? parseInt(parts[2], 10) : 0;
  if (Number.isNaN(hours) || Number.isNaN(minutes) || Number.isNaN(seconds)) return null;
  return hours * 60 + minutes + Math.floor(seconds / 60);
}

function markWithin(arrivals) {
  return arrivals.map((a) => ({
    ...a,
    within: DISPLAY_MAX_MINUTES === 0 ? true : a.minutes <= DISPLAY_MAX_MINUTES,
  }));
}

function lowerBound(arr, value) {
  let lo = 0;
  let hi = arr.length;
  while (lo < hi) {
    const mid = Math.floor((lo + hi) / 2);
    if (arr[mid] < value) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

function routeMatches(route) {
  if (!ROUTE_FILTERS.length) return true;
  const hay = normalize(
    `${route.shortName || ""} ${route.longName || ""} ${route.id || ""}`
  );
  return ROUTE_FILTERS.some((f) => hay.includes(normalize(f)));
}

async function ensureDir(dir) {
  await fs.promises.mkdir(dir, { recursive: true });
}

async function fetchJson(url) {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to fetch ${url} (HTTP ${res.status})`);
  }
  return res.json();
}

async function fetchText(url) {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to fetch ${url} (HTTP ${res.status})`);
  }
  return res.text();
}

async function downloadToFile(url, filePath) {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to download ${url} (HTTP ${res.status})`);
  }
  await ensureDir(path.dirname(filePath));
  const tmpPath = `${filePath}.tmp`;
  const fileStream = fs.createWriteStream(tmpPath);
  const body = res.body ? Readable.fromWeb(res.body) : null;
  await new Promise((resolve, reject) => {
    if (!body) {
      reject(new Error(`Empty response body from ${url}`));
      return;
    }
    body.pipe(fileStream);
    body.on("error", reject);
    fileStream.on("finish", resolve);
  });
  await fs.promises.rename(tmpPath, filePath);
}

async function isFresh(filePath, maxHours) {
  try {
    const stat = await fs.promises.stat(filePath);
    const ageMs = Date.now() - stat.mtimeMs;
    return ageMs < maxHours * 60 * 60 * 1000;
  } catch (err) {
    return false;
  }
}

function findResource(resources, key) {
  const keyLower = key.toLowerCase();
  return resources.find((res) => {
    const name = (res.name || "").toLowerCase();
    const url = (res.url || "").toLowerCase();
    return name === keyLower || url.includes(`/${keyLower}.csv`) || url.includes(`${keyLower}.csv`);
  });
}

async function getGtfsResources() {
  const meta = await fetchJson(
    `https://data.ibb.gov.tr/api/3/action/package_show?id=${GTFS_DATASET}`
  );
  if (!meta.success) {
    throw new Error(`GTFS dataset not found: ${GTFS_DATASET}`);
  }
  const resources = meta.result.resources || [];
  return {
    stops: findResource(resources, "stops"),
    stopTimes: findResource(resources, "stop_times"),
    trips: findResource(resources, "trips"),
    routes: findResource(resources, "routes"),
    calendar: findResource(resources, "calendar"),
    calendarDates: findResource(resources, "calendar_dates"),
  };
}

async function ensureGtfsFiles(state) {
  if (!state.gtfs) state.gtfs = {};
  if (state.gtfs.files) return state.gtfs.files;

  const resources = await getGtfsResources();
  const required = ["stops", "stopTimes", "trips", "routes", "calendar"];
  for (const key of required) {
    if (!resources[key]) {
      throw new Error(`GTFS resource missing: ${key}.csv`);
    }
  }

  await ensureDir(GTFS_CACHE_DIR);
  const files = {};
  const mappings = {
    stops: resources.stops,
    stopTimes: resources.stopTimes,
    trips: resources.trips,
    routes: resources.routes,
    calendar: resources.calendar,
    calendarDates: resources.calendarDates,
  };

  for (const [key, res] of Object.entries(mappings)) {
    if (!res || !res.url) continue;
    const filePath = path.join(GTFS_CACHE_DIR, `${key}.csv`);
    const fresh = await isFresh(filePath, GTFS_CACHE_HOURS);
    if (!fresh) {
      await downloadToFile(res.url, filePath);
    }
    files[key] = filePath;
  }

  state.gtfs.files = files;
  return files;
}

async function loadCalendar(filePath) {
  const calendar = new Map();
  let minStart = null;
  let maxEnd = null;
  await readCsv(
    filePath,
    (row) => {
      if (!row.service_id) return;
      const start = row.start_date;
      const end = row.end_date;
      if (start && (!minStart || start < minStart)) minStart = start;
      if (end && (!maxEnd || end > maxEnd)) maxEnd = end;
      calendar.set(row.service_id, {
        monday: row.monday === "1",
        tuesday: row.tuesday === "1",
        wednesday: row.wednesday === "1",
        thursday: row.thursday === "1",
        friday: row.friday === "1",
        saturday: row.saturday === "1",
        sunday: row.sunday === "1",
        startDate: start,
        endDate: end,
      });
    },
    GTFS_ENCODING
  );
  return { calendar, minStart, maxEnd };
}

async function loadCalendarDates(filePath) {
  const exceptions = new Map();
  if (!filePath) return exceptions;
  await readCsv(filePath, (row) => {
    if (!row.service_id || !row.date || !row.exception_type) return;
    const list = exceptions.get(row.date) || [];
    list.push({
      serviceId: row.service_id,
      exceptionType: row.exception_type,
    });
    exceptions.set(row.date, list);
  }, GTFS_ENCODING);
  return exceptions;
}

function getActiveServiceIds(calendar, exceptions, dateObj) {
  const key = dateKey(dateObj);
  const dow = dateObj.getDay(); // 0=Sun
  const active = new Set();

  for (const [serviceId, svc] of calendar.entries()) {
    if (key < svc.startDate || key > svc.endDate) continue;
    const onDay =
      (dow === 1 && svc.monday) ||
      (dow === 2 && svc.tuesday) ||
      (dow === 3 && svc.wednesday) ||
      (dow === 4 && svc.thursday) ||
      (dow === 5 && svc.friday) ||
      (dow === 6 && svc.saturday) ||
      (dow === 0 && svc.sunday);
    if (onDay) active.add(serviceId);
  }

  const ex = exceptions.get(key) || [];
  for (const item of ex) {
    if (item.exceptionType === "1") active.add(item.serviceId);
    if (item.exceptionType === "2") active.delete(item.serviceId);
  }

  return active;
}

async function loadRoutes(filePath) {
  const routes = new Map();
  await readCsv(filePath, (row) => {
    if (!row.route_id) return;
    routes.set(row.route_id, {
      id: row.route_id,
      shortName: row.route_short_name,
      longName: row.route_long_name,
      type: row.route_type,
      agencyId: row.agency_id,
    });
  }, GTFS_ENCODING);
  return routes;
}

async function loadTrips(filePath, activeServices, routes) {
  const trips = new Map();
  await readCsv(filePath, (row) => {
    if (!row.trip_id || !row.route_id) return;
    if (!activeServices.has(row.service_id)) return;
    const route = routes.get(row.route_id);
    if (!route) return;
    if (!routeMatches(route)) return;
    trips.set(row.trip_id, {
      id: row.trip_id,
      routeId: row.route_id,
      serviceId: row.service_id,
      headsign: row.trip_headsign,
      directionId: row.direction_id,
    });
  }, GTFS_ENCODING);
  return trips;
}

async function loadStops(filePath, stationName) {
  const target = normalize(stationName);
  const stopIds = new Set();
  let displayName = stationName;

  await readCsv(filePath, (row) => {
    const name = row.stop_name || "";
    if (!name) return;
    const norm = normalize(name);
    if (norm === target || norm.includes(target) || target.includes(norm)) {
      stopIds.add(row.stop_id);
      if (!displayName) displayName = name;
    }
  }, GTFS_ENCODING);

  if (!stopIds.size) {
    throw new Error(`Stop '${stationName}' not found in GTFS stops.csv`);
  }

  return { stopIds, displayName };
}

function buildDirectionLabel(route, trip) {
  const base = route.shortName || route.longName || route.id || "Route";
  const headsign = trip.headsign || "";
  if (!headsign) return base;
  if (normalize(headsign).includes(normalize(base))) return headsign;
  return `${base} -> ${headsign}`;
}

async function loadStopTimes(filePath, stopIds, trips, routes) {
  const arrivalsByDirection = new Map();
  await readCsv(filePath, (row) => {
    if (!stopIds.has(row.stop_id)) return;
    const trip = trips.get(row.trip_id);
    if (!trip) return;
    const timeStr = row.arrival_time || row.departure_time;
    const minutes = parseGtfsTimeToMinutes(timeStr);
    if (minutes === null) return;
    const route = routes.get(trip.routeId) || { id: trip.routeId };
    const label = buildDirectionLabel(route, trip);
    const list = arrivalsByDirection.get(label) || [];
    list.push(minutes);
    arrivalsByDirection.set(label, list);
  }, GTFS_ENCODING);

  for (const [label, list] of arrivalsByDirection.entries()) {
    list.sort((a, b) => a - b);
    arrivalsByDirection.set(label, list);
  }

  return arrivalsByDirection;
}

async function getMetroWebConfig(state) {
  const now = Date.now();
  if (state.metroWeb && now - state.metroWeb.fetchedAt < METRO_WEB_CACHE_MINUTES * 60000) {
    return state.metroWeb;
  }
  const html = await fetchText(METRO_WEB_URL);
  const kod = extractKod(html);
  const stations = extractSelectOptions(html, `istasyonlar_${METRO_WEB_LINE_ID}`);
  const routes = extractSelectOptions(html, `seferler_${METRO_WEB_LINE_ID}`);
  if (!stations.length) {
    throw new Error(`Metro web: station list not found for line ${METRO_WEB_LINE_ID}`);
  }
  if (!routes.length) {
    throw new Error(`Metro web: route list not found for line ${METRO_WEB_LINE_ID}`);
  }
  const target = normalize(STATION_NAME);
  const station =
    stations.find((s) => normalize(s.text) === target) ||
    stations.find((s) => normalize(s.text).includes(target));
  if (!station) {
    const names = stations.slice(0, 10).map((s) => s.text).join(", ");
    throw new Error(`Metro web: station '${STATION_NAME}' not found. Examples: ${names}`);
  }
  const routeList = routes.map((r) => ({
    id: r.value,
    label: `M4 ${formatRouteLabel(r.text)}`,
  }));
  const config = {
    stationId: station.value,
    stationName: station.text,
    routes: routeList,
    kod,
    fetchedAt: now,
  };
  state.metroWeb = config;
  return config;
}

function parseSeferTimes(seferList, now) {
  const times = [];
  for (const item of seferList || []) {
    if (item && item.zaman) times.push(item.zaman);
  }
  return markWithin(parseTimes(times, now));
}

async function fetchMetroWebArrivals(state) {
  const config = await getMetroWebConfig(state);
  const now = new Date();
  const headers = {
    Accept: "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
    Origin: "https://www.metro.istanbul",
    Referer: METRO_WEB_URL,
  };

  const requests = config.routes.map(async (route) => {
    const form = new FormData();
    form.append("secim", "1");
    form.append("saat", "");
    form.append("dakika", "");
    form.append("tarih1", "");
    form.append("tarih2", "");
    form.append("station", config.stationId);
    form.append("route", route.id);
    if (config.kod) form.append("kod", config.kod);

    const res = await fetch(METRO_WEB_AJAX, {
      method: "POST",
      headers,
      body: form,
    });
    if (!res.ok) {
      throw new Error(`Metro web request failed (HTTP ${res.status})`);
    }
    const json = await res.json();
    if (json.durum === "-1") {
      throw new Error(json.bilgi || "Metro web returned error");
    }
    const arrivals = parseSeferTimes(json.sefer, now);
    return {
      directionId: route.id,
      directionLabel: route.label,
      arrivals,
    };
  });

  const directions = await Promise.all(requests);
  return { now, stationName: config.stationName, directions };
}

async function buildScheduledData(state, now) {
  const files = await ensureGtfsFiles(state);
  const [calendarData, exceptions, routes] = await Promise.all([
    loadCalendar(files.calendar),
    loadCalendarDates(files.calendarDates),
    loadRoutes(files.routes),
  ]);

  const serviceDateInfo = selectServiceDate(now, calendarData.minStart, calendarData.maxEnd);
  const activeServices = getActiveServiceIds(
    calendarData.calendar,
    exceptions,
    serviceDateInfo.date
  );
  const trips = await loadTrips(files.trips, activeServices, routes);
  const stopInfo = await loadStops(files.stops, STATION_NAME);
  const arrivalsByDirection = await loadStopTimes(
    files.stopTimes,
    stopInfo.stopIds,
    trips,
    routes
  );

  return {
    stopName: stopInfo.displayName || STATION_NAME,
    serviceDate: new Date(now.getFullYear(), now.getMonth(), now.getDate()),
    serviceDateKeyUsed: serviceDateInfo.key,
    serviceDateFallback: serviceDateInfo.fallback,
    serviceDateReason: serviceDateInfo.reason || null,
    calendarRange: { minStart: calendarData.minStart, maxEnd: calendarData.maxEnd },
    arrivalsByDirection,
  };
}

function getUpcomingArrivals(schedule, now) {
  const nowMinutes = Math.floor((now - schedule.serviceDate) / 60000);
  const result = [];

  for (const [label, minutesList] of schedule.arrivalsByDirection.entries()) {
    const idx = lowerBound(minutesList, nowMinutes);
    const upcoming = [];
    for (let i = idx; i < minutesList.length && upcoming.length < SHOW_COUNT; i += 1) {
      const absMinutes = minutesList[i];
      const minutesAway = absMinutes - nowMinutes;
      const time = new Date(schedule.serviceDate.getTime() + absMinutes * 60000);
      const within =
        DISPLAY_MAX_MINUTES === 0 ? true : minutesAway <= DISPLAY_MAX_MINUTES;
      upcoming.push({ minutes: minutesAway, time, within });
    }
    if (upcoming.length) {
      result.push({ directionLabel: label, arrivals: upcoming });
    }
  }

  return result.sort((a, b) => {
    const aMin = a.arrivals[0]?.minutes ?? 0;
    const bMin = b.arrivals[0]?.minutes ?? 0;
    return aMin - bMin;
  });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function normalize(text) {
  return (text || "")
    .toLowerCase()
    .replace(/ı/g, "i")
    .replace(/ğ/g, "g")
    .replace(/ü/g, "u")
    .replace(/ş/g, "s")
    .replace(/ö/g, "o")
    .replace(/ç/g, "c")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]/g, "");
}

function toExtendedLocalISOString(date = new Date()) {
  const pad = (n, z = 2) => String(n).padStart(z, "0");
  const year = date.getFullYear();
  const month = pad(date.getMonth() + 1);
  const day = pad(date.getDate());
  const hour = pad(date.getHours());
  const minute = pad(date.getMinutes());
  const second = pad(date.getSeconds());
  const milliseconds = date.getMilliseconds();
  const subSecond = pad(milliseconds, 3) + "0000";

  const offsetMinutes = -date.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? "+" : "-";
  const offsetHours = pad(Math.floor(Math.abs(offsetMinutes) / 60));
  const offsetMins = pad(Math.abs(offsetMinutes) % 60);

  return `${year}-${month}-${day}T${hour}:${minute}:${second}.${subSecond}${sign}${offsetHours}:${offsetMins}`;
}

function parseHeadersJson(value) {
  if (!value) return {};
  try {
    const parsed = JSON.parse(value);
    if (parsed && typeof parsed === "object") return parsed;
  } catch (_) {
    // Ignore invalid JSON.
  }
  return {};
}

const EXTRA_HEADERS = parseHeadersJson(HEADERS_JSON);

async function apiRequest(method, path, body) {
  const url = `${BASE_URL}${path}`;
  const headers = {
    ...(DISABLE_DEFAULT_HEADERS ? {} : DEFAULT_HEADERS),
    ...EXTRA_HEADERS,
  };
  let payload;
  if (body) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const res = await fetch(url, { method, headers, body: payload });
  const text = await res.text();

  let json;
  try {
    json = JSON.parse(text);
  } catch (err) {
    const snippet = text.replace(/\s+/g, " ").slice(0, 200);
    if (text.includes("Policy Falsified")) {
      throw new Error(
        `API blocked by gateway (Policy Falsified) from ${url} (HTTP ${res.status}). ` +
          "Try running from a Turkey IP, or set METRO_HEADERS_JSON with required headers/keys."
      );
    }
    throw new Error(`Non-JSON response from ${url} (HTTP ${res.status}). Snippet: ${snippet}`);
  }

  if (!json || json.Success !== true) {
    const msg = json && json.Error && json.Error.Message ? json.Error.Message : "Unknown API error";
    throw new Error(`API error from ${url}: ${msg}`);
  }

  return json.Data;
}

async function apiGet(path) {
  return apiRequest("GET", path);
}

async function apiPost(path, body) {
  return apiRequest("POST", path, body);
}

async function getStations() {
  return apiGet("/GetStations");
}

async function getDirections(lineId) {
  return apiGet(`/GetDirectionById/${lineId}`);
}

async function getTimetable(stationId, directionId, now) {
  return apiPost("/GetTimeTable", {
    BoardingStationId: stationId,
    DirectionId: directionId,
    DateTime: toExtendedLocalISOString(now),
  });
}

function parseTimes(times, now) {
  const out = [];
  for (const timeStr of times || []) {
    const parts = timeStr.split(":");
    if (parts.length < 2) continue;
    const hour = parseInt(parts[0], 10);
    const minute = parseInt(parts[1], 10);
    if (Number.isNaN(hour) || Number.isNaN(minute)) continue;

    const d = new Date(now.getTime());
    d.setHours(hour, minute, 0, 0);
    if (d.getTime() < now.getTime() - 60000) {
      d.setDate(d.getDate() + 1);
    }
    const minutes = Math.round((d.getTime() - now.getTime()) / 60000);
    if (minutes >= 0) {
      out.push({ time: d, minutes, label: timeStr });
    }
  }

  out.sort((a, b) => a.minutes - b.minutes);

  const dedup = [];
  const seen = new Set();
  for (const item of out) {
    const key = item.time.toISOString();
    if (seen.has(key)) continue;
    seen.add(key);
    dedup.push(item);
  }
  return dedup;
}

function formatTime(date) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function formatDate(date) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function formatDateTime(date) {
  return `${formatDate(date)} ${formatTime(date)}`;
}

function clearScreen() {
  process.stdout.write("\x1b[2J\x1b[H");
}

function printHeader(title, now) {
  console.log(title);
  console.log(
    `Updated: ${formatDateTime(now)} | Refresh: ${REFRESH_SEC}s | Alert <= ${ALERT_MINUTES} min`
  );
  console.log("-");
}

function printDirection(directionLabel, arrivals) {
  console.log(`Direction: ${directionLabel}`);
  if (!arrivals.length) {
    console.log("  No upcoming trains found.");
    return;
  }
  const within = arrivals.filter((a) => a.within);
  const shown = (within.length ? within : arrivals).slice(0, SHOW_COUNT);
  const line = shown
    .map((a) => {
      const mark = a.within ? "★" : "";
      return `${a.minutes} min (${formatTime(a.time)})${mark}`;
    })
    .join(" | ");
  if (DISPLAY_MAX_MINUTES === 0) {
    console.log(`  Next: ${line}`);
    return;
  }
  if (within.length) {
    console.log(`  Next <= ${DISPLAY_MAX_MINUTES} min: ${line}`);
  } else {
    console.log(`  Next: ${line} (no service within ${DISPLAY_MAX_MINUTES} min)`);
  }
}

function directionLabelFromTimetable(timetable, fallback) {
  if (timetable && timetable.FirstStation && timetable.LastStation) {
    return `${timetable.FirstStation} -> ${timetable.LastStation}`;
  }
  return fallback || "Unknown direction";
}

function beep() {
  if (BEEP) process.stdout.write("\x07");
}

async function resolveStation(lineId, stationName) {
  if (Number.isFinite(STATION_ID_OVERRIDE) && STATION_ID_OVERRIDE > 0) {
    return {
      Id: STATION_ID_OVERRIDE,
      Name: stationName || `Station ${STATION_ID_OVERRIDE}`,
      LineId: lineId,
    };
  }
  const stations = await getStations();
  const target = normalize(stationName);
  const candidates = stations.filter((s) => Number(s.LineId) === Number(lineId));
  const exact = candidates.find((s) => normalize(s.Name) === target);
  if (exact) return exact;
  const partial = candidates.find((s) => normalize(s.Name).includes(target));
  if (partial) return partial;

  const available = candidates.map((s) => s.Name).join(", ");
  throw new Error(
    `Station '${stationName}' not found for line ${lineId}. Available stations: ${available}`
  );
}

async function fetchM4Arrivals(state) {
  const now = new Date();
  const directions = await getDirections(LINE_ID);
  const results = [];

  for (const dir of directions) {
    const timetables = await getTimetable(state.station.Id, dir.DirectionId, now);
    const allArrivals = [];
    for (const tt of timetables || []) {
      allArrivals.push(...parseTimes(tt.TimeInfos?.Times || [], now));
    }
    const label = directionLabelFromTimetable(
      (timetables && timetables[0]) || null,
      dir.DirectionName
    );
    results.push({
      directionId: dir.DirectionId,
      directionLabel: label,
      arrivals: allArrivals,
    });
  }

  return { now, directions: results };
}

function updateAlerts(state, directions) {
  for (const dir of directions) {
    const next = dir.arrivals[0];
    if (!next) continue;
    if (next.minutes <= ALERT_MINUTES) {
      const dirKey = dir.directionId || dir.directionLabel || "dir";
      const key = `${dirKey}:${formatTime(next.time)}`;
      if (state.lastAlertKey !== key) {
        state.lastAlertKey = key;
        beep();
      }
    }
  }
}

function normalizeGroupName(name) {
  const n = normalize(name);
  if (n.startsWith("marmaray")) return "MARMARAY";
  if (n.startsWith("m4")) return "M4";
  return (name || "OTHER").toUpperCase();
}

function groupDirections(directions) {
  const groups = new Map();
  for (const dir of directions) {
    const label = dir.directionLabel || "";
    const base = label.split("->")[0].trim();
    const groupName = normalizeGroupName(base);
    const list = groups.get(groupName) || [];
    list.push(dir);
    groups.set(groupName, list);
  }
  return groups;
}

function printGroupedDirections(directions) {
  const groups = groupDirections(directions);
  const order = ROUTE_FILTERS.length
    ? ROUTE_FILTERS.map((f) => normalizeGroupName(f))
    : Array.from(groups.keys());
  const printed = new Set();

  for (const name of order) {
    console.log(`\n${name}:`);
    const dirs = groups.get(name) || [];
    if (!dirs.length) {
      console.log("  No services found for this line.");
    } else {
      for (const dir of dirs) {
        printDirection(dir.directionLabel, dir.arrivals);
      }
    }
    printed.add(name);
  }

  for (const [name, dirs] of groups.entries()) {
    if (printed.has(name)) continue;
    console.log(`\n${name}:`);
    for (const dir of dirs) {
      printDirection(dir.directionLabel, dir.arrivals);
    }
  }
}

async function mainLoop() {
  const state = {
    station: null,
    lastAlertKey: null,
    mode: MODE,
    schedule: null,
    scheduleDate: null,
    gtfs: null,
    metroWeb: null,
  };

  if (state.mode === "live") {
    try {
      state.station = await resolveStation(LINE_ID, STATION_NAME);
    } catch (err) {
      console.error(`Failed to resolve station: ${err.message}`);
      process.exit(1);
    }
  }

  while (true) {
    let now;
    now = new Date();
    if (state.mode === "metro" || state.mode === "auto") {
      try {
        const metro = await fetchMetroWebArrivals(state);
        now = metro.now;
        clearScreen();
        printHeader(`M4 @ ${metro.stationName}`, now);
        if (!metro.directions.length) {
          console.log("No upcoming services found.");
        } else {
          for (const dir of metro.directions) {
            printDirection(dir.directionLabel, dir.arrivals);
          }
          updateAlerts(state, metro.directions);
        }
      } catch (err) {
        if (state.mode === "auto") {
          state.mode = "scheduled";
          continue;
        }
        clearScreen();
        printHeader(`M4 @ ${STATION_NAME}`, now);
        console.log(`Error: ${err.message}`);
      }
    } else if (state.mode === "scheduled") {
      try {
        const dateKeyNow = dateKey(now);
        if (!state.schedule || state.scheduleDate !== dateKeyNow) {
          state.schedule = await buildScheduledData(state, now);
          state.scheduleDate = dateKeyNow;
        }
        const directions = getUpcomingArrivals(state.schedule, now);
        clearScreen();
        let header = `Scheduled @ ${state.schedule.stopName}`;
        if (state.schedule.serviceDateFallback && state.schedule.serviceDateKeyUsed) {
          header += ` (calendar ${formatDateKey(state.schedule.serviceDateKeyUsed)})`;
        }
        printHeader(header, now);
        if (!directions.length) {
          console.log("No upcoming services found.");
        } else {
          printGroupedDirections(directions);
          updateAlerts(state, directions);
        }
        if (state.schedule.serviceDateFallback && state.schedule.serviceDateReason) {
          console.log(`\nNote: using nearest calendar date because ${state.schedule.serviceDateReason}.`);
        }
      } catch (err) {
        clearScreen();
        printHeader(`Scheduled @ ${STATION_NAME}`, now);
        console.log(`Error: ${err.message}`);
      }
    } else if (state.mode === "live") {
      try {
        if (!state.station) {
          state.station = await resolveStation(LINE_ID, STATION_NAME);
        }
        const m4 = await fetchM4Arrivals(state);
        now = m4.now;
        clearScreen();
        printHeader(`M4 @ ${state.station.Name}`, now);
        for (const dir of m4.directions) {
          printDirection(dir.directionLabel, dir.arrivals);
        }
        updateAlerts(state, m4.directions);
      } catch (err) {
        if (state.mode === "auto") {
          state.mode = "scheduled";
          continue;
        }
        clearScreen();
        now = new Date();
        printHeader(`M4 @ ${state.station ? state.station.Name : STATION_NAME}`, now);
        console.log(`Error: ${err.message}`);
      }
    }

    await sleep(REFRESH_SEC * 1000);
  }
}

mainLoop().catch((err) => {
  console.error(err);
  process.exit(1);
});
