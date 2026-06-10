"""CI guard: refuse PRs that drop brief coverage in site/data/matches.json.

The scheduled refresh-match-data workflow generates a brief for every match
via the briefing agent. If a contributor regenerates matches.json locally
without ANTHROPIC_API_KEY set, every brief comes out null and the merge
silently wipes the populated data on main. This script catches that case
at PR time.

Usage:
    python scripts/check_brief_coverage.py [--min-coverage 0.80] [--path PATH]

Exits 0 if coverage >= threshold, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = REPO_ROOT / "site" / "data" / "matches.json"
DEFAULT_MIN = 0.80


def coverage(path: Path) -> tuple[int, int]:
    data = json.loads(path.read_text())
    matches = data["matches"]
    populated = sum(1 for m in matches if m.get("brief"))
    return populated, len(matches)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--min-coverage", type=float, default=DEFAULT_MIN)
    args = parser.parse_args(argv)

    if not args.path.exists():
        # Nothing to guard: matches.json is intentionally uncommitted (built
        # from provider data, see README). Code-only PRs don't ship it, so its
        # absence is the normal case, not a coverage regression.
        print(f"{args.path} not present — nothing to check, skipping.")
        return 0

    populated, total = coverage(args.path)
    if total == 0:
        print(f"ERROR: {args.path} has no matches", file=sys.stderr)
        return 1

    ratio = populated / total
    print(f"brief coverage: {populated}/{total} = {ratio:.1%}")

    if ratio < args.min_coverage:
        print(
            f"\nFAIL: brief coverage {ratio:.1%} is below threshold "
            f"{args.min_coverage:.0%}.\n\n"
            "This usually means matches.json was regenerated locally without\n"
            "ANTHROPIC_API_KEY set, so every brief came out null. Options:\n"
            "  1. Set ANTHROPIC_API_KEY locally and re-run backend.refresh, OR\n"
            "  2. Revert site/data/matches.json from this PR and let the\n"
            "     scheduled refresh-match-data workflow regenerate it post-merge.\n",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
