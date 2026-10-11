"""Diagnostic records. This module is a contract: see docs/SEMANTICS.md section 6."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Severity = Literal["error", "warning", "info"]


@dataclass(frozen=True)
class Diagnostic:
    """One finding produced by a rule. Identity is (rule, severity, state, column)."""

    rule: str
    severity: Severity
    state: int | None
    column: str | None
    message: str = ""
    path: tuple[int, ...] = ()

    def key(self) -> tuple[str, str, int, str]:
        """Sort/identity key; None sorts first (state -> -1, column -> "")."""
        return (
            self.rule,
            self.severity,
            -1 if self.state is None else self.state,
            "" if self.column is None else self.column,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "state": self.state,
            "column": self.column,
            "message": self.message,
            "path": list(self.path),
        }


@dataclass(frozen=True)
class Report:
    """Result of validating one table. Diagnostics are deduplicated and sorted."""

    table: str
    diagnostics: tuple[Diagnostic, ...]

    @classmethod
    def build(cls, table: str, diagnostics: list[Diagnostic]) -> Report:
        unique: dict[tuple[str, str, int, str], Diagnostic] = {}
        for d in diagnostics:
            unique.setdefault(d.key(), d)
        return cls(table=table, diagnostics=tuple(sorted(unique.values(), key=Diagnostic.key)))

    @property
    def has_errors(self) -> bool:
        return any(d.severity == "error" for d in self.diagnostics)

    def to_dict(self) -> dict[str, object]:
        summary = {
            s: sum(d.severity == s for d in self.diagnostics) for s in ("error", "warning", "info")
        }
        return {
            "table": self.table,
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "summary": summary,
        }
