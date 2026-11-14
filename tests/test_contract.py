"""T46: checks that keep the committed data consistent with docs/CONTRACTS.md (offline, fast).

- every committed target.json under fixtures/ validates against docs/target.schema.json
- every index.json lists folders that exist, and every frame image a target names exists
- web/presets.json (the official test fields) is well formed, with exactly one default
- web/discover.json (T65 quick picks) is well formed and has its provenance
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

REPO = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((REPO / "docs" / "target.schema.json").read_text(encoding="utf-8"))
TARGETS = sorted(REPO.glob("fixtures/**/target.json"))
INDEXES = sorted(REPO.glob("fixtures/**/index.json"))


def test_there_is_something_to_check():
    assert TARGETS and INDEXES


@pytest.mark.parametrize("path", TARGETS, ids=lambda p: str(p.relative_to(REPO)))
def test_fixture_target_validates_and_is_complete(path):
    target = json.loads(path.read_text(encoding="utf-8"))
    jsonschema.validate(target, SCHEMA)
    assert target["id"] == path.parent.name, "id must equal the folder name (CONTRACTS)"
    for frame in target["frames"]:
        assert (path.parent / frame["image"]).is_file(), f"missing frame image {frame['image']}"
    frame_ids = {f["id"] for f in target["frames"]}
    for obj in target.get("known_objects", []) + target.get("labels", []):
        assert {p["frame_id"] for p in obj.get("positions", [])} <= frame_ids
    for det in target.get("detections", []):
        assert {p["frame_id"] for p in det.get("track", [])} <= frame_ids
    if target["synthetic"]:
        assert "synthetic" in target["name"].lower() or "not spherex" in target["name"].lower(), \
            "synthetic fixtures must say so in their name (CLAUDE.md)"


@pytest.mark.parametrize("path", INDEXES, ids=lambda p: str(p.relative_to(REPO)))
def test_index_lists_existing_targets(path):
    index = json.loads(path.read_text(encoding="utf-8"))
    for t in index["targets"]:
        assert (path.parent / t["id"] / "target.json").is_file(), f"index lists {t['id']} but it is missing"


def test_presets():
    fields = json.loads((REPO / "web" / "presets.json").read_text(encoding="utf-8"))["fields"]
    assert len(fields) >= 5
    assert sum(1 for f in fields if f.get("default")) == 1
    for f in fields:
        assert 0 <= f["ra_deg"] < 360 and -90 <= f["dec_deg"] <= 90 and 5 <= f.get("size_arcmin", 15) <= 60, f["name"]


def test_discover():
    d = json.loads((REPO / "web" / "discover.json").read_text(encoding="utf-8"))
    assert d["provenance"] and all({"service", "query", "retrieved_utc"} <= set(p) for p in d["provenance"])
    assert len(d["fields"]) >= 5 and not any(f.get("default") for f in d["fields"])
    for f in d["fields"]:
        assert 0 <= f["ra_deg"] < 360 and -90 <= f["dec_deg"] <= 90 and 5 <= f["size_arcmin"] <= 60, f["name"]
        assert f["group"] and f["why"] and f["coverage"]["epochs"] >= 2, f["name"]


def test_discoveries_sample():
    """T76: the hand-made discovery index validates, is marked synthetic and is what its generator writes."""
    import subprocess
    import sys
    schema = json.loads((REPO / "docs" / "discoveries.schema.json").read_text(encoding="utf-8"))
    path = REPO / "fixtures" / "discoveries-sample.json"
    before = path.read_bytes()
    d = json.loads(before)
    jsonschema.validate(d, schema)
    assert d["synthetic"] is True and len({c["id"] for c in d["candidates"]}) == len(d["candidates"])
    subprocess.run([sys.executable, str(REPO / "fixtures" / "make_discoveries_sample.py")], check=True, capture_output=True)
    assert path.read_bytes() == before, "fixtures/discoveries-sample.json differs from its generator's output"
