"""Command line entry point: python -m pasta [--config FILE]."""

# HOW "python -m pasta" WORKS: Python looks for a file called __main__.py in the "pasta"
# package and runs it. It is the ENTRY POINT of the program (like the file with
# "int main()" in C++).
#
# TWO SEPARATE FUNCTIONS:
# - run(config_path): does the real work (read, validate, draw) and returns the files written.
#   If something goes wrong it RAISES an exception: easy to test.
# - main(argv): the layer that talks to the user. It reads the arguments, calls run, CATCHES
#   the "expected" errors (wrong config, missing Excel file, invalid data, Graphviz not
#   installed) and prints a clear message instead of Python's unreadable traceback.
#   It returns the EXIT CODE: 0 = all good, 1 = error (like "return 1" from main() in C++;
#   scripts and other programs use it to know whether it went well).
# UNEXPECTED errors (bugs in the program) are not caught: there the full traceback is exactly
# what you need to understand what happened.

import argparse
import sys
from datetime import date
from pathlib import Path

import graphviz

from pasta.config import ConfigError, load_config
from pasta.loader import LoadError, load_excel
from pasta.model import Graph, build_graph
from pasta.render_graphviz import render_svg
from pasta.render_html import render_html
from pasta.timeline import compare, take_snapshot
from pasta.validation import DataValidationError, validate

DEFAULT_CONFIG = Path("config.toml")

# TUPLE OF EXCEPTIONS: "except (A, B, C)" catches any of these types, like several C++ catch
# blocks doing the same thing.
# graphviz.ExecutableNotFound is raised if the Graphviz program (dot.exe) is not installed.
EXPECTED_ERRORS = (ConfigError, LoadError, DataValidationError, graphviz.ExecutableNotFound)


def main(argv: list[str] | None = None) -> int:
    """Run the program from the command line and return the exit code."""
    args = _parse_args(argv)
    try:
        written = run(args.config)
    except EXPECTED_ERRORS as error:
        # file=sys.stderr: errors go to "standard error", not to standard output
        # (like std::cerr instead of std::cout in C++).
        print(f"Error: {error}", file=sys.stderr)
        return 1
    for path in written:
        print(f"Written: {path}")
    return 0


def run(config_path: Path) -> list[Path]:
    """Read the configuration and the Excel file, check them, draw the graph(s)."""
    config = load_config(config_path)
    data = load_excel(config.input_file)
    validate(data)  # stops here (DataValidationError) if the Excel file has errors

    # 1. The graph on one date.
    # "a or b": the date from the config, or (if it is None) DateReference from Parametres.
    day = config.snapshot_date or _date_reference(data.parameters)
    graph = build_graph(take_snapshot(data, day), data.parameters)
    # The file name contains the date as YEAR-MONTH-DAY: this way, in alphabetical order,
    # the files are also in date order.
    written = _draw(graph, config.output_dir, f"snapshot_{day:%Y-%m-%d}")

    # 2. The comparison between two dates, only if the config has a [compare] section.
    #    config.py guarantees that before and after are either both present or both missing.
    if config.compare_before and config.compare_after:
        before, after = config.compare_before, config.compare_after
        comparison = build_graph(compare(data, before, after), data.parameters)
        name = f"compare_{before:%Y-%m-%d}_{after:%Y-%m-%d}"
        # "+=" on a list appends ALL the elements of the other list at the end
        # (like vector::insert(end, ...) in C++).
        written += _draw(comparison, config.output_dir, name)
    return written


def _draw(graph: Graph, folder: Path, name: str) -> list[Path]:
    """Draw the graph twice: static image (SVG) and interactive page (HTML)."""
    # Same Graph, two renderers: this is where the model's "one interface, two
    # implementations" idea shows.
    return [
        render_svg(graph, folder / f"{name}.svg"),
        render_html(graph, folder / f"{name}.html"),
    ]


def _date_reference(parameters: dict[str, object]) -> date:
    """Return DateReference from the Parametres sheet, or raise ConfigError."""
    value = parameters.get("DateReference")
    if not isinstance(value, date):
        raise ConfigError(
            "No snapshot_date in the configuration and no valid DateReference in Parametres"
        )
    return value


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Read the command line arguments."""
    # ARGPARSE (standard library) reads the command line arguments, checks them and builds
    # the help by itself: "python -m pasta --help".
    # In C++ you would have to read argc/argv by hand.
    parser = argparse.ArgumentParser(
        prog="python -m pasta",
        description="Draw a company's processes, systems and data flows from an Excel file.",
    )
    # type=Path: the text typed by the user is converted to a Path right away.
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"configuration file (default: {DEFAULT_CONFIG})",
    )
    # argv=None: argparse reads the REAL terminal arguments (sys.argv). Tests pass a list
    # instead, e.g. ["--config", "x.toml"], without needing a terminal.
    return parser.parse_args(argv)


# As in the sample data generator: this block runs only when the file is EXECUTED
# (python -m pasta), not when it is imported (e.g. by the tests).
# sys.exit(code) ends the program and returns the exit code to the terminal.
if __name__ == "__main__":
    sys.exit(main())
