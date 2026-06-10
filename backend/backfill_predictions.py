"""Backfill confirmed-match win predictions into the committed matches.json.

Loads the existing file, computes `prediction` for every confirmed match from
the FIFA ranks already present, and rewrites. TBD matches and every other field
are left untouched; the legacy `prep` key is dropped on load. Idempotent.

Run: python -m backend.backfill_predictions
"""

from __future__ import annotations

from pathlib import Path

from backend.match_prediction import predict_from_fifa_rank
from backend.schema import Status
from backend.writer import load_previous, write_matches_file

REPO_ROOT = Path(__file__).resolve().parents[1]
MATCHES_PATH = REPO_ROOT / "site" / "data" / "matches.json"


def backfill(path: Path = MATCHES_PATH) -> int:
    file = load_previous(path)
    if file is None:
        raise SystemExit(f"no matches file at {path}")
    count = 0
    for m in file.matches:
        if (
            m.status == Status.CONFIRMED
            and m.teams.confirmed is not None
            and len(m.teams.confirmed) == 2
        ):
            a, b = m.teams.confirmed
            m.prediction = predict_from_fifa_rank(a, b, m.phase)
            count += 1
    write_matches_file(file, path)
    return count


if __name__ == "__main__":
    n = backfill()
    print(f"backfilled predictions for {n} confirmed matches")
