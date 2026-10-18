"""Tests for pasta.__main__ (the command line program)."""

import shutil
from pathlib import Path

import pandas as pd
import pytest

from pasta.__main__ import _date_reference, main, run
from pasta.config import ConfigError

SAMPLE_FILE = Path(__file__).resolve().parent.parent / "data" / "sample_pastificio.xlsx"

# These tests really draw the graph: they need Graphviz and dot.exe.
needs_graphviz = pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz not installed")
# (A decorator can be stored in a variable and reused: @needs_graphviz.)


def write_config(folder: Path, input_file: Path, extra: str = "") -> Path:
    """Write a config.toml in folder that reads input_file and writes into folder/out."""
    # as_posix() writes the path with "/" slashes even on Windows: in TOML a backslash "\"
    # between quotes is a special character (as in C++: "\n", "\t"...).
    text = f'input_file = "{input_file.as_posix()}"\noutput_dir = "out"\n{extra}'
    path = folder / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path


@needs_graphviz
def test_run_draws_the_snapshot_of_the_configured_date(tmp_path: Path) -> None:
    config = write_config(tmp_path, SAMPLE_FILE, "snapshot_date = 2027-03-15\n")

    written = run(config)

    out = tmp_path / "out"
    # Each graph is drawn twice: static image (SVG) and interactive page (HTML).
    assert written == [out / "snapshot_2027-03-15.svg", out / "snapshot_2027-03-15.html"]
    # all(...) with a generator expression: True if ALL the files exist.
    assert all(path.exists() for path in written)


@needs_graphviz
def test_date_reference_is_used_when_the_config_has_no_date(tmp_path: Path) -> None:
    written = run(write_config(tmp_path, SAMPLE_FILE))

    # DateReference in the Parametres sheet of the sample file: 2026-10-08
    assert written[0].name == "snapshot_2026-10-08.svg"


@needs_graphviz
def test_run_also_draws_the_comparison_when_configured(tmp_path: Path) -> None:
    compare_section = "[compare]\nbefore = 2026-10-08\nafter = 2027-06-01\n"
    config = write_config(tmp_path, SAMPLE_FILE, compare_section)

    written = run(config)

    # [p.name for p in written]: only the file names, without the folder.
    assert [p.name for p in written] == [
        "snapshot_2026-10-08.svg",
        "snapshot_2026-10-08.html",
        "compare_2026-10-08_2027-06-01.svg",
        "compare_2026-10-08_2027-06-01.html",
    ]
    assert "Changes" in written[2].read_text(encoding="utf-8")  # the subtitle of the comparison


def test_missing_date_reference_is_an_error() -> None:
    with pytest.raises(ConfigError, match="DateReference"):
        _date_reference({})


# CAPSYS: pytest fixture that CAPTURES what the program prints. capsys.readouterr() returns
# an object with .out (standard output, the normal prints) and .err (standard error).
@needs_graphviz
def test_main_returns_0_and_prints_the_file(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    exit_code = main(["--config", str(write_config(tmp_path, SAMPLE_FILE))])

    assert exit_code == 0
    assert "Written:" in capsys.readouterr().out


def test_main_reports_a_missing_config(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    exit_code = main(["--config", str(tmp_path / "nope.toml")])

    assert exit_code == 1
    assert "not found" in capsys.readouterr().err


# CHECK DONE (mutation testing): removing validate() from run(), this test fails with
# "assert 0 == 1". Without validation the program "succeeds" and draws a graph where the wrong
# link DISAPPEARS SILENTLY (the timeline drops links to nodes that do not exist): nobody would
# notice. That is why validation exists.
def test_main_stops_on_invalid_data(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    # Copy of the sample file with an error: a link to a node that does not exist.
    sheets = pd.read_excel(SAMPLE_FILE, sheet_name=None)
    sheets["Liens"].loc[4, "Cible"] = "MIILL"
    broken = tmp_path / "broken.xlsx"
    with pd.ExcelWriter(broken) as writer:
        for name, table in sheets.items():
            table.to_excel(writer, sheet_name=name, index=False)

    exit_code = main(["--config", str(write_config(tmp_path, broken))])

    assert exit_code == 1
    assert "Liens, row 6: Cible 'MIILL' is not an Id in Noeuds" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()  # no drawing if the data is wrong
