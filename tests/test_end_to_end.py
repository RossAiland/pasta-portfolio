"""End-to-end tests: run "python -m pasta" as a real separate program."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

# END-TO-END: the other tests call the Python functions FROM THE INSIDE (run, main). These
# instead do exactly what a user does: they launch "python -m pasta" as a SEPARATE PROGRAM
# and check from the outside the exit code, the printed text and the files produced.
# This way they also cover what the other tests do not touch: the
# "if __name__ == '__main__'" block, sys.exit, the installation of the package.
# They are slower (they start a new Python), so a few are enough.

SAMPLE_FILE = Path(__file__).resolve().parent.parent / "data" / "sample_pastificio.xlsx"

needs_graphviz = pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz not installed")


def run_pasta(*args: str) -> subprocess.CompletedProcess:
    """Run "python -m pasta <args>" in a separate process and return its result."""
    # *args: the function accepts ANY number of arguments, collected in a tuple
    # (like variadic "..." parameters in C++). run_pasta("--config", "x.toml").
    #
    # SUBPROCESS (standard library) launches another program, like std::system/popen in C++.
    # - sys.executable = the path of the Python running the tests (the .venv one):
    #   so the program runs with the same libraries;
    # - capture_output=True: captures what the program prints (stdout and stderr);
    # - text=True, encoding="utf-8": the output arrives as text and not as bytes;
    # - env: the environment variables of the new process. PYTHONIOENCODING=utf-8 forces the
    #   program to print in UTF-8: on the Windows terminal the default encoding is another
    #   one and accents ("Système") would arrive garbled.
    #   {**os.environ, ...} = a copy of the current variables with one more.
    return subprocess.run(
        [sys.executable, "-m", "pasta", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


def write_config(folder: Path, input_file: Path) -> Path:
    path = folder / "config.toml"
    path.write_text(
        f'input_file = "{input_file.as_posix()}"\n'
        'output_dir = "out"\n'
        "[compare]\nbefore = 2026-10-08\nafter = 2027-06-01\n",
        encoding="utf-8",
    )
    return path


@needs_graphviz
def test_the_program_draws_four_files(tmp_path: Path) -> None:
    result = run_pasta("--config", str(write_config(tmp_path, SAMPLE_FILE)))

    assert result.returncode == 0, result.stderr  # if it fails, pytest shows the error
    # sorted(...) returns a SORTED list; .glob("*") = all the files of the folder.
    assert sorted(path.name for path in (tmp_path / "out").glob("*")) == [
        "compare_2026-10-08_2027-06-01.html",
        "compare_2026-10-08_2027-06-01.svg",
        "snapshot_2026-10-08.html",
        "snapshot_2026-10-08.svg",
    ]
    assert result.stdout.count("Written:") == 4


def test_the_program_stops_on_wrong_data(tmp_path: Path) -> None:
    sheets = pd.read_excel(SAMPLE_FILE, sheet_name=None)
    sheets["Noeuds"]["Actif"] = sheets["Noeuds"]["Actif"].astype(object)
    sheets["Noeuds"].loc[5, "Actif"] = "oui"
    broken = tmp_path / "broken.xlsx"
    with pd.ExcelWriter(broken) as writer:
        for name, table in sheets.items():
            table.to_excel(writer, sheet_name=name, index=False)

    result = run_pasta("--config", str(write_config(tmp_path, broken)))

    assert result.returncode == 1
    assert "Noeuds, row 7: Actif must be True or False (found: 'oui')" in result.stderr
    assert "Traceback" not in result.stderr  # a clear message, not Python's traceback
    assert not (tmp_path / "out").exists()


def test_help_works() -> None:
    result = run_pasta("--help")

    assert result.returncode == 0
    assert "--config" in result.stdout
