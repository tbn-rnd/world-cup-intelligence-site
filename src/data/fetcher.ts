import type { MatchesFile } from "../types.js";

export type FetchResult =
  | { kind: "ok"; file: MatchesFile }
  | { kind: "unreachable"; error: string };

export async function fetchMatches(
  url: string,
  fetchImpl: typeof fetch = fetch,
): Promise<FetchResult> {
  try {
    const resp = await fetchImpl(url, { cache: "no-cache" });
    if (!resp.ok) {
      return { kind: "unreachable", error: `HTTP ${resp.status}` };
    }
    const file = (await resp.json()) as MatchesFile;
    return { kind: "ok", file };
  } catch (e) {
    return { kind: "unreachable", error: String(e) };
  }
}
