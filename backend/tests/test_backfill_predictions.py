import json
import shutil
from pathlib import Path

import pytest

from backend.backfill_predictions import backfill
from backend.refresh import main as refresh_main

REPO_ROOT = Path(__file__).resolve().parents[2]
LIVE_MATCHES = REPO_ROOT / "site" / "data" / "matches.json"


@pytest.fixture(scope="module")
def matches_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    if LIVE_MATCHES.exists():
        return LIVE_MATCHES
    # matches.json is generated provider data and isn't committed to the repo.
    # Build the deterministic offline equivalent so these tests run on a
    # fresh clone.
    out = tmp_path_factory.mktemp("backfill") / "matches.json"
    rc = refresh_main(
        ["--offline", "--as-of", "2026-06-20T12:00:00Z", "--output", str(out)]
    )
    assert rc == 0
    return out


def test_backfill_populates_confirmed_and_leaves_tbd(
    tmp_path: Path, matches_file: Path
) -> None:
    target = tmp_path / "matches.json"
    shutil.copy(matches_file, target)
    before = json.loads(target.read_text())
    tbd_before = {
        m["id"]: m["teams"]["tbd_scenarios"]
        for m in before["matches"]
        if m["status"] == "tbd"
    }

    n = backfill(target)
    after = json.loads(target.read_text())

    confirmed = [m for m in after["matches"] if m["status"] == "confirmed"]
    assert n == len(confirmed)
    for m in confirmed:
        pred = m["prediction"]
        assert pred is not None and pred["method"] == "fifa_rank_elo"
        assert len(pred["teams"]) == 2
        total = sum(t["win_prob"] for t in pred["teams"]) + (pred["draw_prob"] or 0.0)
        assert abs(total - 1.0) < 1e-6

    for m in after["matches"]:
        if m["status"] == "tbd":
            assert m["prediction"] is None
            assert m["teams"]["tbd_scenarios"] == tbd_before[m["id"]]
        assert "prep" not in m  # legacy field dropped on load


def test_backfill_is_idempotent(tmp_path: Path, matches_file: Path) -> None:
    target = tmp_path / "matches.json"
    shutil.copy(matches_file, target)
    backfill(target)
    first = target.read_text()
    backfill(target)
    assert target.read_text() == first
