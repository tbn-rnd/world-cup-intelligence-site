/**
 * Time-zone helpers for kickoff display.
 *
 * Each match carries two ISO timestamps in the data: `kickoff_utc` (true
 * instant) and `kickoff_local` (the same instant rendered in the venue's
 * own offset). Both are already-formatted strings — we never parse them
 * with Date for the venue read, because Node's Date applies the host
 * machine's offset and would silently shift the time. Instead we read the
 * wall-clock fields straight out of the ISO string.
 *
 * For non-venue zones (the viewer's browser, US ET/CT/PT, UK), we use
 * Intl.DateTimeFormat against the UTC instant — that's the one path
 * where we genuinely need the runtime's IANA zone database.
 */

const TIME_RE = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/;
const OFFSET_RE = /([Z+-])(?:(\d{2}):(\d{2}))?$/;

export interface TileTimes {
  primary: string;
  secondary: { label: string; time: string } | null;
}

export interface TileTimesInput {
  kickoff_utc: string;
  kickoff_local: string;
  viewerZone?: string;
}

/**
 * The viewer's IANA time zone, e.g. "America/New_York". Falls back to
 * "UTC" if the browser doesn't expose it for any reason.
 */
export function viewerTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone ?? "UTC";
  } catch {
    return "UTC";
  }
}

/**
 * "1:00pm" from a venue-local ISO. We deliberately ignore the offset —
 * the wall-clock hours/minutes ARE the venue time we want to display.
 */
export function formatVenueLocalTime(kickoffLocal: string): string {
  const m = kickoffLocal.match(TIME_RE);
  if (!m) return kickoffLocal;
  return formatHourMinute(parseInt(m[4], 10), parseInt(m[5], 10));
}

/**
 * The trailing offset on a venue-local ISO ("-05:00", "+09:00", "+00:00"
 * for Z). null if the input doesn't end with a recognizable offset.
 */
export function extractVenueOffset(kickoffLocal: string): string | null {
  const m = kickoffLocal.match(OFFSET_RE);
  if (!m) return null;
  if (m[1] === "Z") return "+00:00";
  return `${m[1]}${m[2]}:${m[3]}`;
}

/**
 * "2:00pm" — the UTC instant rendered as wall-clock time in the given
 * IANA zone, using the same lowercase-am/pm shape as formatVenueLocalTime.
 */
export function formatTimeInZone(utcIso: string, ianaZone: string): string {
  const instant = new Date(utcIso);
  if (isNaN(instant.getTime())) return utcIso;
  // hour12: true and our own re-assembly keeps the "1:00pm" shape consistent
  // with formatVenueLocalTime; toLocaleString varies "1:00 PM" / "1:00 p.m."
  // across locales and is hard to normalize otherwise.
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: ianaZone,
    hour: "numeric",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(instant);
  const hour = numFromParts(parts, "hour");
  const minute = numFromParts(parts, "minute");
  if (hour === null || minute === null) return utcIso;
  return formatHourMinute(hour, minute);
}

/**
 * Short tz-abbreviation for the given zone at the given instant —
 * "EDT" / "EST" / "BST" etc. Used as the secondary-time chip label.
 */
export function shortZoneLabel(utcIso: string, ianaZone: string): string {
  const instant = new Date(utcIso);
  if (isNaN(instant.getTime())) return ianaZone;
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: ianaZone,
    timeZoneName: "short",
    hour: "numeric",
  }).formatToParts(instant);
  const name = parts.find((p) => p.type === "timeZoneName")?.value ?? "";
  return name;
}

/**
 * Decide what times to show on a tile date-strip. Primary is always
 * venue-local. Secondary is the viewer's local — UNLESS the viewer is
 * in the same offset as the venue (in which case there's nothing extra
 * to show).
 */
export function tileTimes(input: TileTimesInput): TileTimes {
  const primary = formatVenueLocalTime(input.kickoff_local);
  const zone = input.viewerZone ?? viewerTimeZone();
  // If the viewer's offset for THIS instant matches the venue's offset,
  // both render the same wall clock — drop the secondary.
  if (offsetsMatch(input.kickoff_utc, input.kickoff_local, zone)) {
    return { primary, secondary: null };
  }
  const time = formatTimeInZone(input.kickoff_utc, zone);
  const label = shortZoneLabel(input.kickoff_utc, zone) || "your time";
  return { primary, secondary: { label, time } };
}

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/**
 * "Jun 11" — month + day-of-month parsed straight from the venue-local
 * ISO (no Date construction; we already-know the wall-clock date).
 */
export function venueShortDate(kickoffLocal: string): string {
  const m = kickoffLocal.match(TIME_RE);
  if (!m) return kickoffLocal;
  const month = MONTHS[parseInt(m[2], 10) - 1] ?? "";
  const day = parseInt(m[3], 10);
  return `${month} ${day}`;
}

// ---------- internals ----------

function formatHourMinute(h24: number, mm: number): string {
  const ampm = h24 >= 12 ? "pm" : "am";
  const h12 = ((h24 + 11) % 12) + 1;
  const mmStr = mm < 10 ? `0${mm}` : `${mm}`;
  return `${h12}:${mmStr}${ampm}`;
}

function numFromParts(parts: Intl.DateTimeFormatPart[], type: string): number | null {
  const v = parts.find((p) => p.type === type)?.value;
  if (v === undefined) return null;
  const n = parseInt(v, 10);
  return isNaN(n) ? null : n;
}

function offsetsMatch(utcIso: string, kickoffLocal: string, zone: string): boolean {
  const venueOffset = extractVenueOffset(kickoffLocal);
  if (venueOffset === null) return false;
  const instant = new Date(utcIso);
  if (isNaN(instant.getTime())) return false;
  const viewerOffsetMin = offsetMinutesForZone(instant, zone);
  if (viewerOffsetMin === null) return false;
  const venueOffsetMin = parseOffsetToMinutes(venueOffset);
  return viewerOffsetMin === venueOffsetMin;
}

function parseOffsetToMinutes(offset: string): number {
  // "+09:00", "-05:00", "+00:00"
  const sign = offset.startsWith("-") ? -1 : 1;
  const [hh, mm] = offset.slice(1).split(":").map((x) => parseInt(x, 10));
  return sign * (hh * 60 + mm);
}

function offsetMinutesForZone(instant: Date, ianaZone: string): number | null {
  try {
    // Format the instant in the target zone, then subtract the UTC wall clock.
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone: ianaZone,
      hour12: false,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).formatToParts(instant);
    const y = numFromParts(parts, "year");
    const mo = numFromParts(parts, "month");
    const d = numFromParts(parts, "day");
    let h = numFromParts(parts, "hour");
    const mi = numFromParts(parts, "minute");
    if (y === null || mo === null || d === null || h === null || mi === null) return null;
    // Intl with hour12:false can emit "24" for midnight in some runtimes.
    if (h === 24) h = 0;
    const asIfUTC = Date.UTC(y, mo - 1, d, h, mi);
    return Math.round((asIfUTC - instant.getTime()) / 60000);
  } catch {
    return null;
  }
}
