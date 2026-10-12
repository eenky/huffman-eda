"""State minimization. Implements docs/SEMANTICS.md §9 and the §9.8 API.

T401 lands the precondition and the compatibility half; the search half (§9.4-§9.6) is
added by T402-T404, one module each. Those names are resolved on first attribute access
(PEP 562) rather than imported here, so this file does not change again as each lands and
each task touches only its own module.

While a module is still missing, the error names the task that owns it, so a red golden
run in the interim says which piece is absent instead of failing obscurely.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from huffman_eda.minimize.compat import (
    PRECONDITION_RULES,
    LimitExceeded,
    MinimizationError,
    check_precondition,
    class_set,
    implied,
    incompatibility_reasons,
    incompatible_pairs,
)

__all__ = [
    "PRECONDITION_RULES",
    "LimitExceeded",
    "MinimizationError",
    "check_precondition",
    "class_set",
    "implied",
    "incompatibility_reasons",
    "incompatible_pairs",
    "is_closed_cover",
    "maximal_compatibles",
    "min_closed_cover",
    "minimize",
    "prime_compatibles",
    "reduce",
]

# §9.8 names owned by a later task, mapped to the module that will provide them.
_PENDING: dict[str, str] = {
    "maximal_compatibles": "compatibles",  # T402
    "prime_compatibles": "compatibles",  # T402
    "is_closed_cover": "cover",  # T403
    "min_closed_cover": "cover",  # T403
    "reduce": "reduce",  # T404
    "minimize": "reduce",  # T404
}

# Which task owns each pending module, for the interim error message.
_TASK: dict[str, str] = {"compatibles": "T402", "cover": "T403", "reduce": "T404"}


def __getattr__(name: str) -> Any:
    """Resolve a §9.8 name that a later task owns, on first use (PEP 562).

    Returns ``Any`` because the name's real signature lives in a module that may not
    exist yet; each of those modules is itself checked under ``mypy --strict``.
    """
    module_name = _PENDING.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    try:
        module = import_module(f".{module_name}", __name__)
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            f"{__name__}.{module_name} is not landed yet; {name} arrives with {_TASK[module_name]}"
        ) from exc
    value = getattr(module, name)
    globals()[name] = value  # cache it, so later lookups skip this path
    return value


def __dir__() -> list[str]:
    """Offer the §9.8 names, landed or not, to completion and introspection."""
    return sorted({*globals(), *__all__, *_PENDING})
