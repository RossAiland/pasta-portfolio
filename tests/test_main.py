"""Tests for pasta.__main__ (the command line program)."""

import shutil
from pathlib import Path

import pandas as pd
import pytest

from pasta.__main__ import _date_reference, main, run
from pasta.config import ConfigError

SAMPLE_FILE = Path(__file__).resolve().parent.parent / "data" / "sample_pastificio.xlsx"

# Questi test disegnano davvero il grafo: servono Graphviz e dot.exe.
needs_graphviz = pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz not installed")
# (Un decoratore si può salvare in una variabile e riusare: @needs_graphviz.)


def write_config(folder: Path, input_file: Path, extra: str = "") -> Path:
    """Write a config.toml in folder that reads input_file and writes into folder/out."""
    # as_posix() scrive il percorso con le barre "/" anche su Windows: in TOML la barra
    # rovesciata "\" tra virgolette è un carattere speciale (come in C++: "\n", "\t"...).
    text = f'input_file = "{input_file.as_posix()}"\noutput_dir = "out"\n{extra}'
    path = folder / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path


@needs_graphviz
def test_run_draws_the_snapshot_of_the_configured_date(tmp_path: Path) -> None:
    config = write_config(tmp_path, SAMPLE_FILE, "snapshot_date = 2027-03-15\n")

    written = run(config)

    assert written == [tmp_path / "out" / "snapshot_2027-03-15.svg"]
    assert written[0].exists()


@needs_graphviz
def test_date_reference_is_used_when_the_config_has_no_date(tmp_path: Path) -> None:
    written = run(write_config(tmp_path, SAMPLE_FILE))

    # DateReference del foglio Parametres del file di esempio: 2026-10-08
    assert written[0].name == "snapshot_2026-10-08.svg"


@needs_graphviz
def test_run_also_draws_the_comparison_when_configured(tmp_path: Path) -> None:
    compare_section = "[compare]\nbefore = 2026-10-08\nafter = 2027-06-01\n"
    config = write_config(tmp_path, SAMPLE_FILE, compare_section)

    written = run(config)

    # [p.name for p in written]: solo i nomi dei file, senza la cartella.
    assert [p.name for p in written] == [
        "snapshot_2026-10-08.svg",
        "compare_2026-10-08_2027-06-01.svg",
    ]
    assert "Changes" in written[1].read_text(encoding="utf-8")  # il sottotitolo del confronto


def test_missing_date_reference_is_an_error() -> None:
    with pytest.raises(ConfigError, match="DateReference"):
        _date_reference({})


# CAPSYS: fixture di pytest che CATTURA ciò che il programma stampa. capsys.readouterr()
# restituisce un oggetto con .out (standard output, i print normali) e .err (standard error).
@needs_graphviz
def test_main_returns_0_and_prints_the_file(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    exit_code = main(["--config", str(write_config(tmp_path, SAMPLE_FILE))])

    assert exit_code == 0
    assert "Written:" in capsys.readouterr().out


def test_main_reports_a_missing_config(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    exit_code = main(["--config", str(tmp_path / "nope.toml")])

    assert exit_code == 1
    assert "not found" in capsys.readouterr().err


# PROVA FATTA (mutation testing): togliendo validate() da run(), questo test fallisce con
# "assert 0 == 1". Senza validazione il programma "riesce" e disegna un grafo in cui il link
# sbagliato SPARISCE IN SILENZIO (la timeline scarta i link verso nodi inesistenti): nessuno
# se ne accorgerebbe. È il motivo per cui la validazione c'è.
def test_main_stops_on_invalid_data(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    # Copia del file di esempio con un errore: un link verso un nodo che non esiste.
    sheets = pd.read_excel(SAMPLE_FILE, sheet_name=None)
    sheets["Liens"].loc[4, "Cible"] = "MIILL"
    broken = tmp_path / "broken.xlsx"
    with pd.ExcelWriter(broken) as writer:
        for name, table in sheets.items():
            table.to_excel(writer, sheet_name=name, index=False)

    exit_code = main(["--config", str(write_config(tmp_path, broken))])

    assert exit_code == 1
    assert "Liens, row 6: Cible 'MIILL' is not an Id in Noeuds" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()  # nessun disegno se i dati sono sbagliati
