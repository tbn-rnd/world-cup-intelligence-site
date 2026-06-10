"""Monthly sync of `recent_form_summary` in knowledge/teams.yaml.

For each team in teams.yaml:
  1. Resolve its api-football team ID (cached in knowledge/api_football_team_ids.yaml).
     Uncached teams are first looked up against the World Cup roster — a single
     /fixtures?league=1&season=2026 call enumerates every senior team in one
     response. Falls back to /teams?search=<name> only when the roster lookup
     misses (e.g., a team not in the WC).
  2. Fetch last 5 completed fixtures via /fixtures?team=<id>&season=<year>&last=5.
  3. Ask Claude to write a one-sentence recent_form_summary in the existing brief
     voice, given the team + the 5 fixtures + final scores.
  4. Surgically rewrite the `recent_form_summary:` line for that team in
     teams.yaml — preserving every other line, comment, and formatting decision.

Runs monthly via .github/workflows/sync-recent-form.yml. On any change the
workflow opens a PR for editorial review — summaries are never written
straight to main.

Discovery history: the original /teams?search=<name>-only flow returned
youth/club teams for "United States" and "Congo" during the 2026-06-09 bootstrap.
The roster-first path sidesteps that by anchoring discovery in the actual WC
fixture list, where every team is a senior national side by construction.

All api-football endpoints used here are documented at
https://www.api-football.com/documentation-v3. The parse layer is deliberately
narrow: if the response shape ever changes, this script raises and the workflow
fails cleanly without writing partial state.
"""

# ruff: noqa: E501

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml
from anthropic.types import TextBlockParam
from pydantic import BaseModel

from backend.agents.client import AgentClient

REPO_ROOT = Path(__file__).resolve().parent.parent
TEAMS_PATH = REPO_ROOT / "knowledge" / "teams.yaml"
IDS_PATH = REPO_ROOT / "knowledge" / "api_football_team_ids.yaml"

API_FOOTBALL_BASE = "https://v3.football.api-sports.io"

# Spacer between API calls. 500ms keeps us at ~120 req/min — well under any
# paid api-football tier's per-minute cap (Pro: 300, Ultra: 450, Mega: 900)
# while still giving the server room to breathe. Override via env if needed.
# 429 still gets a Retry-After-aware retry in _get below.
_REQUEST_INTERVAL_S = float(os.environ.get("API_FOOTBALL_THROTTLE_S", "0.5"))

# International matches don't always cluster into one season. Sweep this list
# in order and take the first non-empty response — covers tournaments,
# qualifiers, and friendlies whether the API buckets them under the calendar
# year or the prior-year league season.
_FIXTURE_SEASONS = (
    datetime.now(UTC).year,
    datetime.now(UTC).year - 1,
)

# api-football league ID for the FIFA World Cup. Used at bootstrap time to
# enumerate every senior national side actually playing in the tournament
# via /fixtures?league=1&season=YYYY — sidesteps the youth/club ambiguity
# that /teams?search=<name> has (see the 2026-06-09 bootstrap PR retro).
_WORLD_CUP_LEAGUE_ID = 1
_WORLD_CUP_SEASON = 2026

# api-football's team name doesn't always match teams.yaml's `name` field.
# Add an entry here only when both exact-normalized-name and code-as-name
# lookups miss in the WC roster. Keys are teams.yaml's `name` field; values
# are the api-football roster name.
#
# All entries below are derived from the 2026-06-09 WC-roster dump — see PR
# description on the corrective sync PR. Add new aliases the same way: hit
# /fixtures?league=1&season=2026 once and read off api-football's spelling
# for any team that fails to discover via name + code.
_NAME_ALIASES: dict[str, str] = {
    "United States": "USA",
    "DR Congo": "Congo DR",
    "Bosnia and Herzegovina": "Bosnia & Herzegovina",
    "Côte d'Ivoire": "Ivory Coast",
}


class _Summary(BaseModel):
    summary: str


_SUMMARY_SYSTEM = """You write one-sentence recent-form summaries for a hotel-facing match brief.

Each summary describes a national team's last 5 fixtures in the editorial voice the rest of the brief uses: descriptive, neutral, no operational recommendations, under 25 words. State results compactly; you may name standout opponents or trends. Do NOT use second person, imperatives, or address the property.

Examples of the existing voice (these are the kind of sentence to match):
  - "Coming off 2022 semifinal run; consistently strong African Cup of Nations performance through 2025."
  - "Top-ranked European side; Euro 2024 strong showing; Ronaldo final tournament."
  - "Building toward home World Cup; mixed 2024-25 results, generational squad."

Output a single JSON object: {"summary": "<one sentence>"}. No prose, no code fences.
"""


class ApiFootballClient:
    """Minimal v3 client. Two endpoints, with throttling + 429-aware retry.

    All API calls go through `_get`, which sleeps to space requests across the
    rate-limit window and honors `Retry-After` on 429. A single 429 retry is
    enough for the free tier's per-minute throttle; persistent 429 (the daily
    cap) propagates up so the caller can mark that team as skipped and move on.
    """

    def __init__(self, api_key: str) -> None:
        self._headers = {"x-apisports-key": api_key}
        self._client = httpx.Client(timeout=30.0, headers=self._headers)
        self._last_call_ts: float = 0.0

    def close(self) -> None:
        self._client.close()

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        # Space requests out so we stay under the per-minute rate limit.
        elapsed = time.monotonic() - self._last_call_ts
        if elapsed < _REQUEST_INTERVAL_S:
            time.sleep(_REQUEST_INTERVAL_S - elapsed)
        for attempt in (1, 2):
            self._last_call_ts = time.monotonic()
            resp = self._client.get(f"{API_FOOTBALL_BASE}{path}", params=params)
            if resp.status_code == 429 and attempt == 1:
                retry_after = _parse_retry_after(resp.headers.get("Retry-After"))
                print(f"    429 throttled — sleeping {retry_after}s before retry")
                time.sleep(retry_after)
                continue
            resp.raise_for_status()
            payload = resp.json()
            if not isinstance(payload, dict):
                raise RuntimeError(f"unexpected response shape: {type(payload)}")
            return payload
        raise RuntimeError("unreachable")  # pragma: no cover

    def bootstrap_wc_roster(
        self,
        league_id: int = _WORLD_CUP_LEAGUE_ID,
        season: int = _WORLD_CUP_SEASON,
    ) -> dict[str, int]:
        """Enumerate the World Cup roster via /fixtures?league=...&season=...

        Returns a map of normalized team name → api-football team ID for every
        team appearing in any WC fixture. Group stage covers all 48 teams in a
        single API response, so this guarantees full coverage of senior
        national teams in one call.

        This is the preferred bootstrap path: every team in the response is
        a senior side actually playing in the tournament, sidestepping the
        youth/club ambiguity that /teams?search has.
        """
        data = self._get(
            "/fixtures",
            params={"league": league_id, "season": season},
        )
        roster: dict[str, int] = {}
        for f in data.get("response", []) or []:
            for side in ("home", "away"):
                team = f.get("teams", {}).get(side, {})
                tid = team.get("id")
                tname = team.get("name")
                if isinstance(tid, int) and isinstance(tname, str):
                    roster[_normalize_team_name(tname)] = tid
        return roster

    def discover_team_id_by_search(self, name: str) -> int | None:
        """Fallback discovery via /teams?search=<name>.

        Used only when the WC-roster bootstrap doesn't contain the team — which
        normally means the team isn't in the World Cup, or api-football's name
        for it differs enough from teams.yaml that name + code + alias lookups
        all missed. Prefers entries with `national: true`.

        Kept here because removing it would break maintenance scenarios where
        a team needs to be re-discovered outside the tournament window.
        """
        data = self._get("/teams", params={"search": name})
        candidates = data.get("response", []) or []
        for c in candidates:
            team = c.get("team", {})
            if team.get("national") is True:
                team_id = team.get("id")
                if isinstance(team_id, int):
                    return team_id
        if candidates:
            first = candidates[0].get("team", {}).get("id")
            if isinstance(first, int):
                return first
        return None

    def recent_fixtures(self, team_id: int, n: int = 5) -> list[dict[str, Any]]:
        """Last N completed fixtures for a team across our season sweep.

        api-football's `/fixtures?team=X&last=N` returns nothing for national
        teams unless a season is also pinned, so we try each candidate season
        in order and stop at the first non-empty response.
        """
        for season in _FIXTURE_SEASONS:
            data = self._get(
                "/fixtures",
                params={"team": team_id, "season": season, "last": n},
            )
            response = data.get("response", []) or []
            if not isinstance(response, list):
                raise RuntimeError(f"unexpected /fixtures response shape: {type(response)}")
            if response:
                return response
        return []


def _parse_retry_after(value: str | None) -> int:
    if value is None:
        return 60
    try:
        return max(1, int(float(value)))
    except (TypeError, ValueError):
        return 60


def _normalize_team_name(name: str) -> str:
    """Lowercase + alphanumerics only — for cross-source name matching.

    api-football names ("USA"), teams.yaml names ("United States"), and our
    3-letter codes ("USA") all compare cleanly after this pass.
    """
    return "".join(c for c in name.lower() if c.isalnum())


def resolve_team_id_from_roster(
    name: str,
    code: str,
    roster: dict[str, int],
) -> int | None:
    """Look up a team's api-football ID in the WC roster via name → code → alias.

    Strategy in order:
      1. Exact normalized match on the teams.yaml `name` field.
         Handles the common case (Brazil, France, Germany, etc.).
      2. Match on the 3-letter FIFA code. api-football often uses codes
         like "USA", "BRA" verbatim as the team `name` in tournament rosters.
      3. Match via the _NAME_ALIASES table for the awkward cases where
         neither name nor code lines up.

    Returns None if all three strategies miss — caller falls back to the
    name-search endpoint.
    """
    direct = roster.get(_normalize_team_name(name))
    if direct is not None:
        return direct
    by_code = roster.get(_normalize_team_name(code))
    if by_code is not None:
        return by_code
    alias = _NAME_ALIASES.get(name)
    if alias is not None:
        return roster.get(_normalize_team_name(alias))
    return None


def format_fixtures_for_prompt(fixtures: list[dict[str, Any]]) -> str:
    """Compact, human-readable list of fixtures for the Claude prompt.

    Format per line: `YYYY-MM-DD (League name): Home X-Y Away [STATUS]`. Missing
    fields render as `?` rather than failing — this is downstream context for an
    LLM, not a wire format.
    """
    lines = []
    for f in fixtures:
        date = (f.get("fixture", {}).get("date") or "?")[:10]
        league = f.get("league", {}).get("name") or "?"
        home = f.get("teams", {}).get("home", {}).get("name") or "?"
        away = f.get("teams", {}).get("away", {}).get("name") or "?"
        gh = f.get("goals", {}).get("home")
        ga = f.get("goals", {}).get("away")
        status = f.get("fixture", {}).get("status", {}).get("short") or "?"
        score = f"{gh}-{ga}" if gh is not None and ga is not None else "?-?"
        lines.append(f"  - {date} ({league}): {home} {score} {away} [{status}]")
    return "\n".join(lines)


def generate_summary(
    agent: AgentClient, team_name: str, fixtures: list[dict[str, Any]]
) -> str:
    user_msg = (
        f"Team: {team_name}\n"
        f"Last {len(fixtures)} fixtures (most recent first):\n"
        f"{format_fixtures_for_prompt(fixtures)}"
    )
    prefix: list[TextBlockParam] = [{"type": "text", "text": _SUMMARY_SYSTEM}]
    result = agent.call_structured(
        system_prefix=prefix,
        user_message=user_msg,
        response_model=_Summary,
    )
    return result.summary.strip()


_TEAM_KEY_RE = re.compile(r"^(\s{2})([A-Z]{3}):\s*$")
_FORM_LINE_RE = re.compile(r"^(\s+)recent_form_summary:\s*")


def update_summaries_in_yaml(text: str, updates: dict[str, str]) -> str:
    """Replace each team's `recent_form_summary:` line with the new summary.

    Operates line-by-line on the raw YAML text so the file's comments, ordering,
    and idiosyncratic whitespace are preserved. PyYAML's round-trip would
    reformat the file and drop the curator comments at the top.

    Each summary value is JSON-encoded so backslashes and quotes are escaped
    safely — JSON is a strict subset of YAML's flow scalar form.
    """
    out: list[str] = []
    current_team: str | None = None
    for line in text.splitlines(keepends=True):
        team_match = _TEAM_KEY_RE.match(line.rstrip("\n").rstrip("\r"))
        if team_match:
            current_team = team_match.group(2)
            out.append(line)
            continue
        form_match = _FORM_LINE_RE.match(line)
        if form_match and current_team in updates:
            indent = form_match.group(1)
            new_value = json.dumps(updates[current_team], ensure_ascii=False)
            out.append(f"{indent}recent_form_summary: {new_value}\n")
            continue
        out.append(line)
    return "".join(out)


def load_team_ids() -> dict[str, int]:
    if not IDS_PATH.exists():
        return {}
    data = yaml.safe_load(IDS_PATH.read_text()) or {}
    ids = data.get("team_ids", {}) or {}
    return {k: int(v) for k, v in ids.items()}


def save_team_ids(ids: dict[str, int]) -> None:
    payload = {
        "team_ids": dict(sorted(ids.items())),
    }
    header = (
        "# Cached api-football team IDs, keyed by FIFA 3-letter code.\n"
        "# Populated automatically by backend/sync_recent_form.py on first run.\n"
        "# Delete an entry to force re-discovery of that team's ID.\n\n"
    )
    IDS_PATH.write_text(header + yaml.safe_dump(payload, sort_keys=False))


def main() -> int:
    api_key = os.environ.get("API_FOOTBALL_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("error: API_FOOTBALL_KEY not set", file=sys.stderr)
        return 2
    if not anthropic_key:
        print("error: ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 2

    teams_text = TEAMS_PATH.read_text()
    teams_data = yaml.safe_load(teams_text)
    teams = teams_data.get("teams", {})

    cached_ids = load_team_ids()
    api = ApiFootballClient(api_key)
    agent = AgentClient(anthropic_key)

    # Bootstrap the World Cup roster once. Every team participating in
    # league=1 season=2026 falls out of a single /fixtures call, with senior
    # IDs only — no name-search ambiguity. Cached IDs short-circuit this
    # lookup; the roster is only consulted for teams that aren't cached yet.
    wc_roster: dict[str, int] = {}
    if any(code not in cached_ids for code in teams):
        try:
            wc_roster = api.bootstrap_wc_roster()
            print(f"Loaded {len(wc_roster)} senior teams from WC league={_WORLD_CUP_LEAGUE_ID} roster")
        except httpx.HTTPError as exc:
            print(f"WC-roster bootstrap failed: {exc} — discovery will fall back to /teams?search")

    updates: dict[str, str] = {}
    new_ids = dict(cached_ids)
    skipped: list[str] = []

    try:
        for code in sorted(teams.keys()):
            team = teams[code]
            name = team.get("name") or code

            team_id = cached_ids.get(code)
            if team_id is None:
                # 1. Prefer the WC roster — guaranteed senior teams, one API
                #    call for all 48 teams.
                team_id = resolve_team_id_from_roster(name, code, wc_roster)
                # 2. Fall back to name-search only if the roster lookup missed.
                #    Mostly happens when api-football's WC roster isn't
                #    populated yet for a given season or when a team's name
                #    doesn't match any of name/code/alias.
                if team_id is None:
                    try:
                        team_id = api.discover_team_id_by_search(name)
                    except httpx.HTTPError as exc:
                        print(f"  {code} ({name}): discovery failed — {exc}")
                        skipped.append(code)
                        continue
                if team_id is None:
                    print(f"  {code} ({name}): no api-football team ID found — skipping")
                    skipped.append(code)
                    continue
                new_ids[code] = team_id
                print(f"  {code} ({name}): discovered api-football ID {team_id}")

            try:
                fixtures = api.recent_fixtures(team_id)
            except httpx.HTTPError as exc:
                print(f"  {code} ({name}): fetch failed — {exc}")
                skipped.append(code)
                continue

            if not fixtures:
                print(f"  {code} ({name}): no fixtures returned — leaving summary as-is")
                continue

            try:
                summary = generate_summary(agent, name, fixtures)
            except Exception as exc:
                print(f"  {code} ({name}): summary generation failed — {exc}")
                skipped.append(code)
                continue

            updates[code] = summary
            preview = summary if len(summary) < 80 else summary[:77] + "..."
            print(f"  {code} ({name}): {preview}")
    finally:
        api.close()
        # Always checkpoint the IDs we managed to discover and the summaries
        # we managed to generate — even if the loop bailed out partway. Next
        # run picks up from the cached IDs instead of re-burning lookups.
        if updates:
            new_text = update_summaries_in_yaml(teams_text, updates)
            TEAMS_PATH.write_text(new_text)
        if new_ids != cached_ids:
            save_team_ids(new_ids)

    print(
        f"\nSynced {len(updates)} summaries"
        f" · {len(new_ids) - len(cached_ids)} new IDs"
        f" · {len(skipped)} skipped"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
