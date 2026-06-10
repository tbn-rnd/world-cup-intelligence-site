"""Write matches.json to disk and load the previous file for diffing."""

from pathlib import Path

from backend.schema import MatchesFile


def write_matches_file(file: MatchesFile, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = file.model_dump_json(indent=2, exclude_none=False)
    path.write_text(serialized + "\n")


def load_previous(path: Path) -> MatchesFile | None:
    if not path.exists():
        return None
    raw = path.read_text()
    return MatchesFile.model_validate_json(raw)
