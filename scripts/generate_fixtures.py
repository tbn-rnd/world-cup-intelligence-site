"""Regenerate knowledge/fixtures_2026.yaml from the canonical 2026 schedule.

Source of truth: the published 2026 World Cup schedule, cross-verified between
NBC Sports and FOX Sports public reporting in November 2025 - June 2026. All
72 group-stage team pairings and venue assignments are official; all 32
knockout slots have official venue/date/kickoff but team feeders are TBD
until the group stage resolves.

Kickoff times throughout are reported by NBC/FOX in US Eastern time. This script
converts them to each venue's local timezone (and to UTC) using a static UTC
offset map — accurate for June/July 2026 (all US/CA cities observe DST; Mexico
does not).

Run:  uv run python scripts/generate_fixtures.py
Output: knowledge/fixtures_2026.yaml
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = REPO_ROOT / "knowledge" / "fixtures_2026.yaml"


class CityMeta(NamedTuple):
    prefix: str
    display: str
    venue: str
    utc_offset_hours: int  # June/July 2026 (DST already factored in)


# Venue metadata keyed by short alphanumeric handle used in the schedule below.
CITIES: dict[str, CityMeta] = {
    "atl": CityMeta("atl", "Atlanta", "Mercedes-Benz Stadium", -4),
    "bos": CityMeta("bos", "Boston", "Gillette Stadium", -4),
    "dal": CityMeta("dal", "Dallas", "AT&T Stadium", -5),
    "gdl": CityMeta("gdl", "Guadalajara", "Estadio Akron", -6),
    "hou": CityMeta("hou", "Houston", "NRG Stadium", -5),
    "kan": CityMeta("kan", "Kansas City", "Arrowhead Stadium", -5),
    "lax": CityMeta("lax", "Los Angeles", "SoFi Stadium", -7),
    "mex": CityMeta("mex", "Mexico City", "Estadio Azteca", -6),
    "mia": CityMeta("mia", "Miami", "Hard Rock Stadium", -4),
    "mty": CityMeta("mty", "Monterrey", "Estadio BBVA", -6),
    "nyj": CityMeta("nyj", "NY/NJ", "MetLife Stadium", -4),
    "phi": CityMeta("phi", "Philadelphia", "Lincoln Financial Field", -4),
    "sea": CityMeta("sea", "Seattle", "Lumen Field", -7),
    "sfo": CityMeta("sfo", "San Francisco Bay Area", "Levi's Stadium", -7),
    "tor": CityMeta("tor", "Toronto", "BMO Field", -4),
    "van": CityMeta("van", "Vancouver", "BC Place", -7),
}

# US Eastern time offset in June/July 2026: UTC-4 (EDT).
ET_OFFSET = -4


def et_to_local_utc(
    et_date: str, et_hour: int, et_minute: int, city: CityMeta
) -> tuple[str, str]:
    """Convert (ET date + ET clock time) to (local-time ISO, UTC ISO) at city.

    Returns the local-time string with the city's UTC offset suffix and the UTC
    string (Z-suffixed). Handles day rollovers in both directions.
    """
    et_dt = datetime.fromisoformat(f"{et_date}T{et_hour:02d}:{et_minute:02d}:00") \
        .replace(tzinfo=timezone(timedelta(hours=ET_OFFSET)))
    utc_dt = et_dt.astimezone(timezone.utc)
    local_dt = et_dt.astimezone(timezone(timedelta(hours=city.utc_offset_hours)))
    return (
        local_dt.strftime("%Y-%m-%dT%H:%M:%S") + _fmt_offset(city.utc_offset_hours),
        utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def _fmt_offset(hours: int) -> str:
    sign = "+" if hours >= 0 else "-"
    return f"{sign}{abs(hours):02d}:00"


def local_date_at_city(et_date: str, et_hour: int, et_minute: int, city: CityMeta) -> str:
    """Return YYYY-MM-DD of the kickoff in the venue's local timezone.

    Used to build IDs so the date in the ID reflects when the match is played
    locally (matches existing convention in the file).
    """
    et_dt = datetime.fromisoformat(f"{et_date}T{et_hour:02d}:{et_minute:02d}:00") \
        .replace(tzinfo=timezone(timedelta(hours=ET_OFFSET)))
    local_dt = et_dt.astimezone(timezone(timedelta(hours=city.utc_offset_hours)))
    return local_dt.strftime("%Y-%m-%d")


# ----------------------------------------------------------------------
# GROUP STAGE — 72 matches, all official.
# Each row: (ET_date, ET_hour, ET_minute, city_key, group, team_a, team_b)
# Times are NBC/FOX-reported US Eastern; midnight ET entries are intentional
# (late-evening Pacific-time kickoffs in the published schedule).
# ----------------------------------------------------------------------
GROUP_STAGE: list[tuple[str, int, int, str, str, str, str]] = [
    # Matchday 1 (Jun 11)
    ("2026-06-11", 15, 0, "mex", "A", "MEX", "RSA"),
    ("2026-06-11", 22, 0, "gdl", "A", "KOR", "CZE"),
    # Matchday 1 (Jun 12)
    ("2026-06-12", 15, 0, "tor", "B", "CAN", "BIH"),
    ("2026-06-12", 21, 0, "lax", "D", "USA", "PAR"),
    # Matchday 1 (Jun 13)
    ("2026-06-13",  0, 0, "van", "D", "AUS", "TUR"),  # Vancouver late slot (~Jun 12 21:00 PT)
    ("2026-06-13", 15, 0, "sfo", "B", "QAT", "SUI"),
    ("2026-06-13", 18, 0, "nyj", "C", "BRA", "MAR"),
    ("2026-06-13", 21, 0, "bos", "C", "HAI", "SCO"),
    # Matchday 1 (Jun 14)
    ("2026-06-14", 13, 0, "hou", "E", "GER", "CUW"),
    ("2026-06-14", 16, 0, "dal", "F", "NED", "JPN"),
    ("2026-06-14", 19, 0, "phi", "E", "CIV", "ECU"),
    ("2026-06-14", 22, 0, "mty", "F", "SWE", "TUN"),
    # Matchday 1 (Jun 15)
    ("2026-06-15", 12, 0, "atl", "H", "ESP", "CPV"),
    ("2026-06-15", 15, 0, "sea", "G", "BEL", "EGY"),
    ("2026-06-15", 18, 0, "mia", "H", "KSA", "URU"),
    ("2026-06-15", 21, 0, "lax", "G", "IRN", "NZL"),
    # Matchday 1 (Jun 16)
    ("2026-06-16",  0, 0, "sfo", "J", "AUT", "JOR"),  # SF late slot (~Jun 15 21:00 PT)
    ("2026-06-16", 15, 0, "nyj", "I", "FRA", "SEN"),
    ("2026-06-16", 18, 0, "bos", "I", "IRQ", "NOR"),
    ("2026-06-16", 21, 0, "kan", "J", "ARG", "ALG"),
    # Matchday 1 (Jun 17)
    ("2026-06-17", 13, 0, "hou", "K", "POR", "COD"),
    ("2026-06-17", 16, 0, "dal", "L", "ENG", "CRO"),
    ("2026-06-17", 19, 0, "tor", "L", "GHA", "PAN"),
    ("2026-06-17", 22, 0, "mex", "K", "UZB", "COL"),

    # Matchday 2 (Jun 18)
    ("2026-06-18", 12, 0, "atl", "A", "CZE", "RSA"),
    ("2026-06-18", 15, 0, "lax", "B", "SUI", "BIH"),
    ("2026-06-18", 18, 0, "van", "B", "CAN", "QAT"),
    ("2026-06-18", 21, 0, "gdl", "A", "MEX", "KOR"),
    # Matchday 2 (Jun 19)
    ("2026-06-19",  0, 0, "sfo", "D", "TUR", "PAR"),  # SF late slot (~Jun 18 21:00 PT)
    ("2026-06-19", 15, 0, "sea", "D", "USA", "AUS"),
    ("2026-06-19", 18, 0, "bos", "C", "SCO", "MAR"),
    ("2026-06-19", 21, 0, "phi", "C", "BRA", "HAI"),
    # Matchday 2 (Jun 20)
    ("2026-06-20",  0, 0, "mty", "F", "TUN", "JPN"),  # Monterrey late slot (~Jun 19 22:00 CT)
    ("2026-06-20", 13, 0, "hou", "F", "NED", "SWE"),
    ("2026-06-20", 16, 0, "tor", "E", "GER", "CIV"),
    ("2026-06-20", 20, 0, "kan", "E", "ECU", "CUW"),
    # Matchday 2 (Jun 21)
    ("2026-06-21", 12, 0, "atl", "H", "ESP", "KSA"),
    ("2026-06-21", 15, 0, "lax", "G", "BEL", "IRN"),
    ("2026-06-21", 18, 0, "mia", "H", "URU", "CPV"),
    ("2026-06-21", 21, 0, "van", "G", "NZL", "EGY"),
    # Matchday 2 (Jun 22)
    ("2026-06-22", 13, 0, "dal", "J", "ARG", "AUT"),
    ("2026-06-22", 17, 0, "phi", "I", "FRA", "IRQ"),
    ("2026-06-22", 20, 0, "nyj", "I", "NOR", "SEN"),
    ("2026-06-22", 23, 0, "sfo", "J", "JOR", "ALG"),
    # Matchday 2 (Jun 23)
    ("2026-06-23", 13, 0, "hou", "K", "POR", "UZB"),
    ("2026-06-23", 16, 0, "bos", "L", "ENG", "GHA"),
    ("2026-06-23", 19, 0, "tor", "L", "PAN", "CRO"),
    ("2026-06-23", 22, 0, "gdl", "K", "COL", "COD"),

    # Matchday 3 (Jun 24)
    ("2026-06-24", 15, 0, "van", "B", "SUI", "CAN"),
    ("2026-06-24", 15, 0, "sea", "B", "BIH", "QAT"),
    ("2026-06-24", 18, 0, "mia", "C", "SCO", "BRA"),
    ("2026-06-24", 18, 0, "atl", "C", "MAR", "HAI"),
    ("2026-06-24", 21, 0, "mex", "A", "CZE", "MEX"),
    ("2026-06-24", 21, 0, "mty", "A", "RSA", "KOR"),
    # Matchday 3 (Jun 25)
    ("2026-06-25", 16, 0, "nyj", "E", "ECU", "GER"),
    ("2026-06-25", 16, 0, "phi", "E", "CUW", "CIV"),
    ("2026-06-25", 19, 0, "kan", "F", "TUN", "NED"),
    ("2026-06-25", 19, 0, "dal", "F", "JPN", "SWE"),
    ("2026-06-25", 22, 0, "lax", "D", "TUR", "USA"),
    ("2026-06-25", 22, 0, "sfo", "D", "PAR", "AUS"),
    # Matchday 3 (Jun 26)
    ("2026-06-26", 15, 0, "bos", "I", "NOR", "FRA"),
    ("2026-06-26", 15, 0, "tor", "I", "SEN", "IRQ"),
    ("2026-06-26", 20, 0, "gdl", "H", "URU", "ESP"),
    ("2026-06-26", 20, 0, "hou", "H", "CPV", "KSA"),
    ("2026-06-26", 23, 0, "van", "G", "NZL", "BEL"),
    ("2026-06-26", 23, 0, "sea", "G", "EGY", "IRN"),
    # Matchday 3 (Jun 27)
    ("2026-06-27", 17, 0, "nyj", "L", "PAN", "ENG"),
    ("2026-06-27", 17, 0, "phi", "L", "CRO", "GHA"),
    ("2026-06-27", 19, 30, "mia", "K", "COL", "POR"),
    ("2026-06-27", 19, 30, "atl", "K", "COD", "UZB"),
    ("2026-06-27", 22, 0, "kan", "J", "ALG", "AUT"),
    ("2026-06-27", 22, 0, "dal", "J", "JOR", "ARG"),
]

# ----------------------------------------------------------------------
# KNOCKOUT STAGE — 32 slots. host_city / venue / kickoff are official;
# team feeders resolve from bracket_2026.yaml after group stage ends.
# Each row: (ET_date, ET_hour, ET_minute, city_key, phase, bracket_slot,
#            decision_date)
#
# bracket_slot numbers correspond to the official published match numbers
# (M73-M104 per Wikipedia and the official bracket chart). The numbering
# reflects bracket
# position, NOT chronology — e.g. M74 (Boston, Jun 29 4:30pm) plays after M76
# (Houston, Jun 29 1pm).
# ----------------------------------------------------------------------
KNOCKOUTS: list[tuple[str, int, int, str, str, str, str]] = [
    # ROUND OF 32 (decision_date = end of group stage, Jun 27)
    ("2026-06-28", 15, 0, "lax", "round_of_32", "r32_match_73", "2026-06-27"),  # A2 vs B2
    ("2026-06-29", 13, 0, "hou", "round_of_32", "r32_match_76", "2026-06-27"),  # C1 vs F2
    ("2026-06-29", 16, 30, "bos", "round_of_32", "r32_match_74", "2026-06-27"),  # E1 vs 3rd
    ("2026-06-29", 21, 0, "mty", "round_of_32", "r32_match_75", "2026-06-27"),  # F1 vs C2
    ("2026-06-30", 13, 0, "dal", "round_of_32", "r32_match_78", "2026-06-27"),  # E2 vs I2
    ("2026-06-30", 17, 0, "nyj", "round_of_32", "r32_match_77", "2026-06-27"),  # I1 vs 3rd
    ("2026-06-30", 21, 0, "mex", "round_of_32", "r32_match_79", "2026-06-27"),  # A1 vs 3rd
    ("2026-07-01", 12, 0, "atl", "round_of_32", "r32_match_80", "2026-06-27"),  # L1 vs 3rd
    ("2026-07-01", 16, 0, "sea", "round_of_32", "r32_match_82", "2026-06-27"),  # G1 vs 3rd
    ("2026-07-01", 20, 0, "sfo", "round_of_32", "r32_match_81", "2026-06-27"),  # D1 vs 3rd
    ("2026-07-02", 15, 0, "lax", "round_of_32", "r32_match_84", "2026-06-27"),  # H1 vs J2
    ("2026-07-02", 19, 0, "tor", "round_of_32", "r32_match_83", "2026-06-27"),  # K2 vs L2
    ("2026-07-02", 23, 0, "van", "round_of_32", "r32_match_85", "2026-06-27"),  # B1 vs 3rd
    ("2026-07-03", 14, 0, "dal", "round_of_32", "r32_match_88", "2026-06-27"),  # D2 vs G2
    ("2026-07-03", 18, 0, "mia", "round_of_32", "r32_match_86", "2026-06-27"),  # J1 vs H2
    ("2026-07-03", 21, 30, "kan", "round_of_32", "r32_match_87", "2026-06-27"),  # K1 vs 3rd

    # ROUND OF 16 (decision_date = end of R32, Jul 3)
    ("2026-07-04", 13, 0, "hou", "round_of_16", "r16_match_90", "2026-07-03"),  # W73 vs W75
    ("2026-07-04", 17, 0, "phi", "round_of_16", "r16_match_89", "2026-07-03"),  # W74 vs W77
    ("2026-07-05", 16, 0, "nyj", "round_of_16", "r16_match_91", "2026-07-03"),  # W76 vs W78
    ("2026-07-05", 20, 0, "mex", "round_of_16", "r16_match_92", "2026-07-03"),  # W79 vs W80
    ("2026-07-06", 15, 0, "dal", "round_of_16", "r16_match_93", "2026-07-03"),  # W83 vs W84
    ("2026-07-06", 20, 0, "sea", "round_of_16", "r16_match_94", "2026-07-03"),  # W81 vs W82
    ("2026-07-07", 12, 0, "atl", "round_of_16", "r16_match_95", "2026-07-03"),  # W86 vs W88
    ("2026-07-07", 16, 0, "van", "round_of_16", "r16_match_96", "2026-07-03"),  # W85 vs W87

    # QUARTER-FINALS (decision_date = end of R16, Jul 7)
    ("2026-07-09", 16, 0, "bos", "quarter_final", "qf_match_97", "2026-07-07"),
    ("2026-07-10", 15, 0, "lax", "quarter_final", "qf_match_98", "2026-07-07"),
    ("2026-07-11", 17, 0, "mia", "quarter_final", "qf_match_99", "2026-07-07"),
    ("2026-07-11", 21, 0, "kan", "quarter_final", "qf_match_100", "2026-07-07"),

    # SEMI-FINALS (decision_date = end of QFs, Jul 11)
    ("2026-07-14", 15, 0, "dal", "semi_final", "sf_match_101", "2026-07-11"),
    ("2026-07-15", 15, 0, "atl", "semi_final", "sf_match_102", "2026-07-11"),

    # BRONZE FINAL (decision_date = end of SFs, Jul 15)
    ("2026-07-18", 16, 0, "mia", "bronze_final", "bronze_match_103", "2026-07-15"),

    # FINAL (decision_date = end of SFs, Jul 15)
    ("2026-07-19", 15, 0, "nyj", "final", "final_match_104", "2026-07-15"),
]


PHASE_TO_SLUG = {
    "round_of_32": "r32",
    "round_of_16": "r16",
    "quarter_final": "qf",
    "semi_final": "sf",
    "bronze_final": "bronze",
    "final": "final",
}


def build_group_entry(row: tuple) -> str:
    et_date, et_h, et_m, city_key, group, team_a, team_b = row
    city = CITIES[city_key]
    local_date = local_date_at_city(et_date, et_h, et_m, city)
    local_iso, utc_iso = et_to_local_utc(et_date, et_h, et_m, city)
    match_id = f"{city.prefix}-{local_date}-grp{group}-{team_a.lower()}-{team_b.lower()}"
    return (
        f"  - id: {match_id}\n"
        f'    kickoff_local: "{local_iso}"\n'
        f'    kickoff_utc: "{utc_iso}"\n'
        f"    host_city: {city.display}\n"
        f"    venue: {city.venue}\n"
        f"    phase: group_stage\n"
        f"    status: confirmed\n"
        f"    group: {group}\n"
        f"    confirmed_teams: [{team_a}, {team_b}]\n"
    )


def build_knockout_entry(row: tuple) -> str:
    et_date, et_h, et_m, city_key, phase, slot, decision = row
    city = CITIES[city_key]
    local_date = local_date_at_city(et_date, et_h, et_m, city)
    local_iso, utc_iso = et_to_local_utc(et_date, et_h, et_m, city)
    slot_suffix = slot.replace("_", "-")
    match_id = f"{city.prefix}-{local_date}-{slot_suffix}"
    return (
        f"  - id: {match_id}\n"
        f'    kickoff_local: "{local_iso}"\n'
        f'    kickoff_utc: "{utc_iso}"\n'
        f"    host_city: {city.display}\n"
        f"    venue: {city.venue}\n"
        f"    phase: {phase}\n"
        f"    status: tbd\n"
        f"    bracket_slot: {slot}\n"
        f'    decision_date: "{decision}"\n'
    )


def main() -> None:
    header = (
        "# Full 2026 World Cup schedule (104 matches).\n"
        "# Source: the official 2026 World Cup match schedule released after\n"
        "# the Final Draw (2025-12-05), cross-verified between NBC Sports and FOX\n"
        "# Sports public reporting. Group-stage team-to-venue assignments are\n"
        "# official. Knockout host_city / venue / kickoff are\n"
        "# official; team feeders resolve via bracket_2026.yaml.\n"
        "#\n"
        "# Kickoff times are stored in venue-local timezone (kickoff_local) and\n"
        "# UTC (kickoff_utc). June/July 2026 offsets: US Eastern UTC-4,\n"
        "# US Central UTC-5, US Pacific UTC-7, Mexico UTC-6 year-round.\n"
        "#\n"
        "# This file is generated by scripts/generate_fixtures.py. Edit the\n"
        "# script's GROUP_STAGE / KNOCKOUTS tables and re-run, do not hand-edit.\n"
        "#\n"
        "# Counts (must equal):\n"
        "#   group_stage: 72   round_of_32: 16   round_of_16: 8\n"
        "#   quarter_final: 4  semi_final: 2     bronze_final: 1   final: 1\n"
        "#   TOTAL: 104\n"
        "\n"
        'tournament: "World Cup 2026"\n'
        "\n"
        "matches:\n"
    )

    sections: list[str] = []

    # Group stage broken into matchdays for readability.
    md1 = [r for r in GROUP_STAGE if r[0] <= "2026-06-17"]
    md2 = [r for r in GROUP_STAGE if "2026-06-18" <= r[0] <= "2026-06-23"]
    md3 = [r for r in GROUP_STAGE if r[0] >= "2026-06-24"]

    sections.append(
        "\n  # ===================================================================\n"
        "  # GROUP STAGE — Matchday 1 (Jun 11–17)\n"
        "  # ===================================================================\n"
    )
    sections.extend("\n" + build_group_entry(r) for r in md1)

    sections.append(
        "\n  # ===================================================================\n"
        "  # GROUP STAGE — Matchday 2 (Jun 18–23)\n"
        "  # ===================================================================\n"
    )
    sections.extend("\n" + build_group_entry(r) for r in md2)

    sections.append(
        "\n  # ===================================================================\n"
        "  # GROUP STAGE — Matchday 3 (Jun 24–27)\n"
        "  # ===================================================================\n"
    )
    sections.extend("\n" + build_group_entry(r) for r in md3)

    # Knockouts grouped by phase.
    by_phase: dict[str, list[tuple]] = {}
    for r in KNOCKOUTS:
        by_phase.setdefault(r[4], []).append(r)

    phase_titles = {
        "round_of_32": "ROUND OF 32 (Jun 28 – Jul 3)",
        "round_of_16": "ROUND OF 16 (Jul 4 – Jul 7)",
        "quarter_final": "QUARTER-FINALS (Jul 9 – Jul 11)",
        "semi_final": "SEMI-FINALS (Jul 14 – Jul 15)",
        "bronze_final": "BRONZE FINAL (Jul 18)",
        "final": "FINAL (Jul 19)",
    }

    for phase_key, title in phase_titles.items():
        rows = by_phase.get(phase_key, [])
        if not rows:
            continue
        sections.append(
            "\n  # ===================================================================\n"
            f"  # {title}\n"
            "  # ===================================================================\n"
        )
        sections.extend("\n" + build_knockout_entry(r) for r in rows)

    OUT_PATH.write_text(header + "".join(sections))

    # Sanity-check counts.
    counts: dict[str, int] = {}
    for r in GROUP_STAGE:
        counts["group_stage"] = counts.get("group_stage", 0) + 1
    for r in KNOCKOUTS:
        counts[r[4]] = counts.get(r[4], 0) + 1

    expected = {
        "group_stage": 72,
        "round_of_32": 16,
        "round_of_16": 8,
        "quarter_final": 4,
        "semi_final": 2,
        "bronze_final": 1,
        "final": 1,
    }
    print(f"wrote {OUT_PATH.relative_to(REPO_ROOT)}")
    print(f"counts: {counts}")
    assert counts == expected, f"phase counts off: got {counts}, expected {expected}"
    print(f"phase counts OK (total {sum(counts.values())})")


if __name__ == "__main__":
    main()
