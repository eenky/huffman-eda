"""State assignment. Implements docs/SEMANTICS.md §10 and the §10.8 API.

T501 lands the encoded table and the race analysis, T502 the dichotomy and cover search, T503 the
excitation functions and decoding. Those names are resolved on first attribute access (PEP 562)
rather than imported here, because importing a submodule sets it as an attribute of its package —
``tracey`` is both a module and a function, and the function is what §10.8 promises.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "PRECONDITION_RULES",
    "Assignment",
    "AssignmentError",
    "Dichotomies",
    "EncodedTable",
    "ExcitationTable",
    "LimitExceeded",
    "assign",
    "check_precondition",
    "critical_races",
    "decode",
    "defined_codes",
    "dichotomies",
    "encode",
    "excitation",
    "tracey",
]

# §10.8 names owned by a module, mapped to the module that provides them.
_OWNERS: dict[str, tuple[str, ...]] = {
    "encoded": (
        "PRECONDITION_RULES",
        "AssignmentError",
        "LimitExceeded",
        "EncodedTable",
        "check_precondition",
        "encode",
        "defined_codes",
    ),
    "races": ("critical_races",),
    "tracey": ("Dichotomies", "Assignment", "dichotomies", "tracey", "assign"),
    "excitation": ("ExcitationTable", "excitation", "decode"),
}

_OWNED_BY: dict[str, str] = {name: module for module, names in _OWNERS.items() for name in names}


def _bind(module_name: str) -> None:
    """Bind every §10.8 name that module owns into this package.

    Importing a submodule sets it as an attribute of its package, so a module whose name matches
    one of its functions (``tracey``) would otherwise shadow that function.
    """
    module = import_module(f".{module_name}", __name__)
    for name in _OWNERS[module_name]:
        globals()[name] = getattr(module, name)


def __getattr__(name: str) -> Any:
    """Resolve a §10.8 name on first use (PEP 562).

    Returns ``Any`` because the name's real signature lives in a module that may not exist yet;
    each of those modules is itself checked under ``mypy --strict``.
    """
    module_name = _OWNED_BY.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    try:
        _bind(module_name)
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            f"{__name__}.{module_name} is not landed yet; {name} arrives with its task"
        ) from exc
    return globals()[name]


def __dir__() -> list[str]:
    """Offer the §10.8 names, landed or not, to completion and introspection."""
    return sorted({*globals(), *__all__, *_OWNED_BY})
