from huffman_eda import __version__
from huffman_eda.diagnostics import Diagnostic, Report


def test_version() -> None:
    assert __version__


def test_report_dedupes_and_sorts() -> None:
    a = Diagnostic("FT008", "warning", 2, None)
    b = Diagnostic("FT002", "error", 1, "1")
    report = Report.build("t", [a, b, a])
    assert [d.rule for d in report.diagnostics] == ["FT002", "FT008"]
    assert report.has_errors
