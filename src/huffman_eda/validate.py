"""The validate() entry point. Implements docs/SEMANTICS.md §5 and §6."""

from __future__ import annotations

from huffman_eda.diagnostics import Report
from huffman_eda.explore import explore
from huffman_eda.model import FlowTable
from huffman_eda.rules.dynamic import dynamic_rules
from huffman_eda.rules.static import static_rules

__all__ = ["validate"]


def validate(table: FlowTable) -> Report:
    """Every static and dynamic diagnostic for ``table``, deduplicated and sorted."""
    result = explore(table)
    diagnostics = [*static_rules(table), *dynamic_rules(table, result)]
    return Report.build(table.name, diagnostics)
