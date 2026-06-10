import type { DataFreshness, TournamentPhase } from "../types.js";

export const POPULARITY_LABEL: Record<"popular" | "moderate" | "standard", string> = {
  popular: "Popular",
  moderate: "Moderate",
  standard: "Standard",
};

export function formatProbability(p: number): string {
  return `${(p * 100).toFixed(1)}%`;
}

/**
 * Value-driven solid fill for probability bars. Heatmap palette:
 *   gray   = long shot   (low probability — noise)
 *   coral  = credible    (mid probability)
 *   red    = dominant    (high probability)
 * The visible feeder-distribution data tops out around 55%, so we stretch
 * the color curve (t = p / 0.55) so a 55%+ pick reaches the red end of
 * the palette instead of stalling in coral.
 */
export function probabilityBarBackground(p: number): string {
  const t = Math.max(0, Math.min(1, p / 0.55));
  type Stop = readonly [number, readonly [number, number, number]];
  const stops: readonly Stop[] = [
    [0.0, [200, 205, 215]], // cool gray — long shot
    [0.5, [220, 130,  90]], // warm coral — credible
    [1.0, [200,  50,  50]], // crimson red — dominant favorite
  ];
  let lo = stops[0];
  let hi = stops[stops.length - 1];
  for (let i = 1; i < stops.length; i++) {
    if (t <= stops[i][0]) {
      lo = stops[i - 1];
      hi = stops[i];
      break;
    }
  }
  const span = hi[0] - lo[0] || 1;
  const k = (t - lo[0]) / span;
  const lerp = (a: number, b: number) => Math.round(a + (b - a) * k);
  const r = lerp(lo[1][0], hi[1][0]);
  const g = lerp(lo[1][1], hi[1][1]);
  const b = lerp(lo[1][2], hi[1][2]);
  return `rgb(${r}, ${g}, ${b})`;
}

export function formatLocalKickoff(iso: string): string {
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  if (!m) return iso;
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const month = months[parseInt(m[2], 10) - 1];
  const day = parseInt(m[3], 10);
  const h24 = parseInt(m[4], 10);
  const mm = m[5];
  const ampm = h24 >= 12 ? "PM" : "AM";
  const h12 = ((h24 + 11) % 12) + 1;
  return `${month} ${day} · ${h12}:${mm} ${ampm}`;
}

const FRESH_THRESHOLD_MS: Record<TournamentPhase, number> = {
  pre_tournament: 60 * 60 * 1000,
  group_stage: 45 * 60 * 1000,
  round_of_32: 20 * 60 * 1000,
  round_of_16: 20 * 60 * 1000,
  quarter_finals: 20 * 60 * 1000,
  semi_finals: 20 * 60 * 1000,
  finals: 20 * 60 * 1000,
};

export function computeWallClockFreshness(
  generatedAtIso: string,
  serverFreshness: DataFreshness,
  phase: TournamentPhase,
  now: Date = new Date(),
): DataFreshness {
  if (serverFreshness === "unreachable") return "unreachable";
  const generatedAt = new Date(generatedAtIso);
  const ageMs = now.getTime() - generatedAt.getTime();
  const threshold = FRESH_THRESHOLD_MS[phase];
  if (ageMs > threshold) return "stale";
  return serverFreshness;
}

export function formatRelativeTime(generatedAtIso: string, now: Date = new Date()): string {
  const generatedAt = new Date(generatedAtIso);
  const ageSec = Math.floor((now.getTime() - generatedAt.getTime()) / 1000);
  if (ageSec < 60) return `${ageSec}s ago`;
  if (ageSec < 3600) return `${Math.floor(ageSec / 60)}m ago`;
  return `${Math.floor(ageSec / 3600)}h ago`;
}

/**
 * Absolute refresh timestamp for the header — local browser time,
 * with the user's short timezone abbreviation appended so a reader
 * in Atlanta doesn't have to guess whether "9:28 PM" is Atlanta time
 * or some server clock.
 * Format: "May 17 · 8:41 PM EDT".
 *
 * `viewerZone` is exposed for test pinning; defaults to the browser's
 * resolved IANA zone at runtime.
 */
export function formatRefreshTimestamp(
  generatedAtIso: string,
  viewerZone?: string,
): string {
  const d = new Date(generatedAtIso);
  if (isNaN(d.getTime())) return generatedAtIso;
  const zone = viewerZone ?? safeViewerZone();
  // Use Intl in the target zone for every component so a pinned
  // viewerZone produces deterministic output regardless of where the
  // test runner happens to live.
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: zone,
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    timeZoneName: "short",
  }).formatToParts(d);
  const month = parts.find((p) => p.type === "month")?.value ?? "";
  const day = parts.find((p) => p.type === "day")?.value ?? "";
  const hour = parts.find((p) => p.type === "hour")?.value ?? "";
  const minute = parts.find((p) => p.type === "minute")?.value ?? "";
  const dayPeriod = (parts.find((p) => p.type === "dayPeriod")?.value ?? "").toUpperCase();
  const tzName = parts.find((p) => p.type === "timeZoneName")?.value ?? "";
  const stamp = `${month} ${day} · ${hour}:${minute} ${dayPeriod}`;
  return tzName ? `${stamp} ${tzName}` : stamp;
}

function safeViewerZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone ?? "UTC";
  } catch {
    return "UTC";
  }
}
