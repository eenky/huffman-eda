"""Tests for the Gray-code column order (T201)."""

from __future__ import annotations

from itertools import pairwise

import pytest

from huffman_eda.gray import gray_columns


def test_two_inputs_is_the_documented_order() -> None:
    assert gray_columns(2) == ["00", "01", "11", "10"]


@pytest.mark.parametrize("n", range(1, 7))
def test_every_column_appears_once(n: int) -> None:
    columns = gray_columns(n)
    assert len(columns) == 2**n
    assert len(set(columns)) == 2**n
    assert all(len(column) == n for column in columns)
    assert set(columns) == {format(k, f"0{n}b") for k in range(2**n)}


@pytest.mark.parametrize("n", range(1, 7))
def test_consecutive_columns_differ_in_exactly_one_bit(n: int) -> None:
    columns = gray_columns(n)
    cyclic = columns + columns[:1]  # the wraparound step is a single change too
    for before, after in pairwise(cyclic):
        assert sum(a != b for a, b in zip(before, after, strict=True)) == 1, (before, after)


def test_lexicographic_order_is_not_gray_order() -> None:
    # Guards the §7 distinction: machine output is lexicographic, display is Gray.
    assert gray_columns(2) != sorted(gray_columns(2))


@pytest.mark.parametrize("n", [0, -1])
def test_rejects_tables_without_inputs(n: int) -> None:
    with pytest.raises(ValueError, match="at least one input"):
        gray_columns(n)
