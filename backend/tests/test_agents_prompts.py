from pathlib import Path

from backend.agents.prompts import (
    build_briefing_prefix,
)


def test_briefing_prefix_includes_cache_control(knowledge_dir: Path) -> None:
    prefix = build_briefing_prefix(knowledge_dir=knowledge_dir)
    # Last block should carry cache_control=ephemeral so the prefix is cached
    last = prefix[-1]
    assert last.get("cache_control") == {"type": "ephemeral"}


def test_briefing_prefix_contains_curated_knowledge(knowledge_dir: Path) -> None:
    prefix = build_briefing_prefix(knowledge_dir=knowledge_dir)
    combined = " ".join(block.get("text", "") for block in prefix)
    assert "briefing" in combined.lower()
    assert "MEX" in combined or "Mexico" in combined
    assert "curated" in combined.lower()


def test_prefix_blocks_are_well_typed(knowledge_dir: Path) -> None:
    """Each block has type='text' and a string 'text' field; cache_control optional."""
    for builder in (build_briefing_prefix,):
        prefix = builder(knowledge_dir=knowledge_dir)
        assert len(prefix) >= 2  # system prompt + at least one knowledge block
        for block in prefix:
            assert block["type"] == "text"
            assert isinstance(block["text"], str)
            assert block["text"]  # non-empty
