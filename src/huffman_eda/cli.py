"""The ``hfe`` command line. Implements docs/SEMANTICS.md §6.

Four commands over the M1/M2 pipeline, and the §6 exit codes for all of them:

- ``0`` nothing to report — no ``error`` diagnostic
- ``1`` at least one ``error`` diagnostic
- ``2`` usage error, a file that cannot be read, or a ``ParseError``

A ``ParseError`` is reported as ``FILE:ROW:COLUMN: reason`` with empty fields when the
error is not attached to one entry.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from huffman_eda.diagnostics import Report
from huffman_eda.explore import explore
from huffman_eda.graph_export import to_dot, to_json
from huffman_eda.io import ParseError, dump_table, load_markdown, load_table
from huffman_eda.model import FlowTable
from huffman_eda.render import render_rich, render_text
from huffman_eda.validate import validate

__all__ = ["app"]

OK = 0
DIAGNOSTICS = 1
USAGE = 2

_FILE_HELP = "flow table: .yaml, .yml or .json"

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Verification-first toolkit for Huffman-model asynchronous circuits.",
)

FileArgument = Annotated[Path, typer.Argument(metavar="FILE", help=_FILE_HELP)]
MarkdownArgument = Annotated[
    Path, typer.Argument(metavar="FILE", help="Markdown transcription: .md")
]
OutputOption = Annotated[Path, typer.Option("-o", "--output", help="YAML file to write")]
JsonOption = Annotated[bool, typer.Option("--json", help="print Report.to_dict() instead")]
PlainOption = Annotated[bool, typer.Option("--plain", help="plain text instead of a rich table")]
FormatOption = Annotated[str, typer.Option("--format", help="json or dot")]
CheckOption = Annotated[bool, typer.Option("--check", help="report instead of printing")]


def _load(path: Path) -> FlowTable:
    """Load a table, turning any §2 violation into exit code 2."""
    try:
        return load_table(path)
    except ParseError as error:
        typer.echo(f"{path}:{_field(error.row)}:{_field(error.column)}: {error.reason}", err=True)
        raise typer.Exit(USAGE) from error


def _load_markdown(path: Path) -> FlowTable:
    """Load a Markdown transcription, turning any §2 violation into exit code 2."""
    try:
        return load_markdown(path)
    except ParseError as error:
        typer.echo(f"{path}:{_field(error.row)}:{_field(error.column)}: {error.reason}", err=True)
        raise typer.Exit(USAGE) from error


def _field(value: object) -> str:
    """A ``FILE:ROW:COLUMN`` field, empty when the error has no location."""
    return "" if value is None else str(value)


def _summary(report: Report) -> str:
    counts = {
        severity: sum(d.severity == severity for d in report.diagnostics)
        for severity in ("error", "warning", "info")
    }
    return (
        f"{report.table}: {len(report.diagnostics)} diagnostic(s) "
        f"({counts['error']} error, {counts['warning']} warning, {counts['info']} info)"
    )


def _exit(report: Report) -> None:
    """Exit with the §6 code for this report."""
    raise typer.Exit(DIAGNOSTICS if report.has_errors else OK)


@app.command("validate")
def validate_command(
    file: FileArgument,
    json_output: JsonOption = False,
) -> None:
    """Report every FT rule finding for FILE."""
    report = validate(_load(file))
    if json_output:
        typer.echo(json.dumps(report.to_dict(), indent=2))
    else:
        typer.echo(_summary(report))
        for diagnostic in report.diagnostics:
            typer.echo(
                f"  {diagnostic.rule} {diagnostic.severity:7} "
                f"({diagnostic.state},{diagnostic.column})  {diagnostic.message}"
            )
    _exit(report)


@app.command("view")
def view_command(
    file: FileArgument,
    plain: PlainOption = False,
) -> None:
    """Show FILE as a §7 grid."""
    table = _load(file)
    report = validate(table)
    if plain:
        typer.echo(render_text(table), nl=False)
    else:
        Console().print(render_rich(table))
    _exit(report)


@app.command("explore")
def explore_command(
    file: FileArgument,
    output_format: FormatOption = "json",
) -> None:
    """Walk FILE from its reset entry and print the behaviour graph."""
    table = _load(file)
    report = validate(table)
    if output_format == "json":
        typer.echo(json.dumps(to_json(explore(table)), indent=2))
    elif output_format == "dot":
        typer.echo(to_dot(table, explore(table)), nl=False)
    else:
        typer.echo(f"unknown format {output_format!r}: expected 'json' or 'dot'", err=True)
        raise typer.Exit(USAGE)
    _exit(report)


@app.command("fmt")
def fmt_command(
    file: FileArgument,
    check: CheckOption = False,
) -> None:
    """Re-serialize FILE in the canonical §2 form."""
    table = _load(file)
    canonical = dump_table(table)
    if check:
        same = file.read_text(encoding="utf-8") == canonical
        typer.echo(f"{file}: {'canonical' if same else 'would be reformatted'}")
    else:
        typer.echo(canonical, nl=False)
    _exit(validate(table))


@app.command("import")
def import_command(
    file: MarkdownArgument,
    output: OutputOption,
) -> None:
    """Convert a Markdown transcription into canonical YAML."""
    table = _load_markdown(file)
    report = validate(table)
    output.write_text(dump_table(table), encoding="utf-8")
    typer.echo(f"wrote {output}")
    _exit(report)
