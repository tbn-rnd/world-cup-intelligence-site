import type { MatchesFile } from "../types.js";

export function signaturesByMatchId(file: MatchesFile): Map<string, string> {
  const map = new Map<string, string>();
  for (const m of file.matches) map.set(m.id, m.signature);
  return map;
}

export function changedMatchIds(
  previous: MatchesFile | null,
  next: MatchesFile,
): string[] {
  if (previous === null) return next.matches.map((m) => m.id);
  const prev = signaturesByMatchId(previous);
  return next.matches
    .filter((m) => prev.get(m.id) !== m.signature)
    .map((m) => m.id);
}
