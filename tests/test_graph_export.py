"""Tests for the behaviour graph export (T202)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from huffman_eda.explore import explore
from huffman_eda.graph_export import flipped_bit, sink_id, to_dot, to_json
from huffman_eda.io import load_table
from huffman_eda.model import Cell, Choice, FlowTable

GOLDEN = Path(__file__).parent / "golden"
SNAPSHOTS = Path(__file__).parent / "snapshots"
CASES = sorted(p for p in GOLDEN.iterdir() if p.is_dir())

SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["reset_ok", "nodes", "edges"],
    "additionalProperties": False,
    "properties": {
        "reset_ok": {"type": "boolean"},
        "nodes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["state", "column"],
                "additionalProperties": False,
                "properties": {"state": {"type": "integer"}, "column": {"type": "string"}},
            },
        },
        "edges": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "src_state",
                    "src_column",
                    "dst_column",
                    "flipped",
                    "outcome",
                    "path",
                    "final",
                    "cycle",
                ],
                "additionalProperties": False,
                "properties": {
                    "src_state": {"type": "integer"},
                    "src_column": {"type": "string"},
                    "dst_column": {"type": "string"},
                    "flipped": {"type": "integer"},
                    "outcome": {"enum": ["stable", "oscillation", "undefined", "nondet"]},
                    "path": {"type": "array", "items": {"type": "integer"}},
                    "final": {"type": "integer"},
                    "cycle": {"type": "array", "items": {"type": "integer"}},
                },
            },
        },
    },
}


def validate(schema: dict[str, Any], instance: Any, path: str = "$") -> None:
    """The JSON Schema subset this file uses: type, required, properties, items, enum."""
    if "enum" in schema:
        assert instance in schema["enum"], f"{path}: {instance!r} is not one of {schema['enum']}"
    kind = schema.get("type")
    if kind is None:
        return
    if kind == "object":
        assert isinstance(instance, dict), f"{path}: expected an object, got {instance!r}"
        for key in schema.get("required", []):
            assert key in instance, f"{path}: missing required key {key!r}"
        properties = schema.get("properties", {})
        for key, value in instance.items():
            if key in properties:
                validate(properties[key], value, f"{path}.{key}")
            else:
                assert schema.get("additionalProperties") is not False, f"{path}: {key!r} extra"
    elif kind == "array":
        assert isinstance(instance, list), f"{path}: expected an array, got {instance!r}"
        for index, item in enumerate(instance):
            validate(schema["items"], item, f"{path}[{index}]")
    elif kind == "integer":
        assert isinstance(instance, int) and not isinstance(instance, bool), f"{path}: not an int"
    elif kind == "string":
        assert isinstance(instance, str), f"{path}: expected a string, got {instance!r}"
    elif kind == "boolean":
        assert isinstance(instance, bool), f"{path}: expected a boolean, got {instance!r}"


def snapshot(path: Path, produced: str) -> None:
    """Compare against the stored snapshot, or rewrite it when asked to."""
    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(produced, encoding="utf-8")
        return
    assert path.exists(), f"missing snapshot; run UPDATE_SNAPSHOTS=1 pytest {__file__}"
    assert path.read_text(encoding="utf-8") == produced


def loaded(case: Path) -> tuple[FlowTable, dict[str, object]]:
    table = load_table(case / "table.yaml")
    return table, to_json(explore(table))


# --- snapshots and schema ----------------------------------------------------


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.name)
def test_json_matches_snapshot(case: Path) -> None:
    _, exported = loaded(case)
    snapshot(SNAPSHOTS / f"{case.name}.json", json.dumps(exported, indent=2) + "\n")


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.name)
def test_dot_matches_snapshot(case: Path) -> None:
    table = load_table(case / "table.yaml")
    snapshot(SNAPSHOTS / f"{case.name}.dot", to_dot(table, explore(table)))


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.name)
def test_json_validates_against_the_schema(case: Path) -> None:
    _, exported = loaded(case)
    validate(SCHEMA, exported)
    json.dumps(exported)  # JSON-ready by construction


def test_the_schema_validator_itself_rejects_bad_output() -> None:
    """Guards the guard: the schema must be able to fail."""
    with pytest.raises(AssertionError):
        validate(SCHEMA, {"reset_ok": "yes", "nodes": [], "edges": []})
    with pytest.raises(AssertionError):
        validate(SCHEMA, {"reset_ok": True, "nodes": [{"state": 1}], "edges": []})
    with pytest.raises(AssertionError):
        validate(SCHEMA, {"reset_ok": True, "nodes": [], "edges": [], "extra": 1})


# --- determinism -------------------------------------------------------------


def test_output_is_deterministic_and_sorted() -> None:
    table = load_table(GOLDEN / "incomplete_2in" / "table.yaml")
    result = explore(table)
    exported = to_json(result)
    assert exported == to_json(result)
    edges = exported["edges"]
    assert isinstance(edges, list)
    assert [(e["src_state"], e["src_column"], e["dst_column"]) for e in edges] == sorted(
        (e["src_state"], e["src_column"], e["dst_column"]) for e in edges
    )
    nodes = exported["nodes"]
    assert isinstance(nodes, list)
    assert [(n["state"], n["column"]) for n in nodes] == sorted(
        (n["state"], n["column"]) for n in nodes
    )


def test_json_describes_each_probe() -> None:
    table = load_table(GOLDEN / "oscillation" / "table.yaml")
    exported = to_json(explore(table))
    edges = exported["edges"]
    assert isinstance(edges, list)
    assert len(edges) == 1
    edge = edges[0]
    assert edge["src_state"] == 1
    assert (edge["src_column"], edge["dst_column"], edge["flipped"]) == ("0", "1", 0)
    assert edge["outcome"] == "oscillation"
    assert edge["path"] == [1, 2]
    assert edge["cycle"] == [1, 2]
    assert edge["final"] == 2


def test_empty_walk_still_exports() -> None:
    table = FlowTable(
        name="t", inputs=("x",), outputs=("z",), reset=(7, "0"), rows={1: {"0": Cell()}}
    )
    result = explore(table)
    assert to_json(result) == {"reset_ok": False, "nodes": [], "edges": []}
    assert to_dot(table, result) == "digraph behavior {\n  rankdir=LR;\n  node [shape=box];\n}\n"


# --- DOT ---------------------------------------------------------------------


def test_dot_uses_solid_edges_for_settled_probes_and_red_sinks_otherwise() -> None:
    table = load_table(GOLDEN / "incomplete_2in" / "table.yaml")
    dot = to_dot(table, explore(table))
    assert 'n_1_00 [label="1@00 / 0"];' in dot
    assert 'n_1_00 -> n_2_01 [label="x2"];' in dot  # settled: plain edge
    assert 'n_1_00 -> sink_undefined [label="x1", style=dashed, color=red];' in dot
    assert 'sink_undefined [label="UNDEFINED", shape=oval, color=red, fontcolor=red];' in dot
    assert dot.count("sink_undefined") == 3  # one declaration, two uses
    assert dot.count("style=dashed") == dot.count("sink_undefined") - 1


def test_dot_label_omits_outputs_when_there_are_none() -> None:
    table = FlowTable(
        name="t",
        inputs=("x",),
        outputs=(),
        reset=(1, "0"),
        rows={1: {"0": Cell((Choice(1, ""),)), "1": Cell((Choice(1, ""),))}},
    )
    assert 'n_1_0 [label="1@0"];' in to_dot(table, explore(table))


def test_dot_node_ids_are_graphviz_safe() -> None:
    table = load_table(GOLDEN / "clean_toggle" / "table.yaml")
    dot = to_dot(table, explore(table))
    declarations = [line.strip().split(" ")[0] for line in dot.splitlines() if "[label=" in line]
    assert declarations
    assert all(name.startswith(("n_", "sink_")) for name in declarations)
    assert sink_id("OSCILLATION") == "sink_oscillation"


def test_flipped_bit_finds_the_changed_input() -> None:
    assert flipped_bit("00", "10") == 0
    assert flipped_bit("00", "01") == 1
    assert flipped_bit("0110", "1110") == 0
    with pytest.raises(ValueError, match="not adjacent"):
        flipped_bit("00", "11")
    with pytest.raises(ValueError, match="not adjacent"):
        flipped_bit("00", "000")
