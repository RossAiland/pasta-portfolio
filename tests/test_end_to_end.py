"""End-to-end tests: run "python -m pasta" as a real separate program."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

# END-TO-END: gli altri test chiamano le funzioni Python DALL'INTERNO (run, main). Questi
# invece fanno esattamente ciò che fa un utente: lanciano "python -m pasta" come PROGRAMMA
# SEPARATO e controllano dall'esterno codice di uscita, testo stampato e file prodotti.
# Così verificano anche ciò che gli altri test non toccano: il blocco
# "if __name__ == '__main__'", sys.exit, l'installazione del package.
# Sono più lenti (avviano un nuovo Python), quindi ne bastano pochi.

SAMPLE_FILE = Path(__file__).resolve().parent.parent / "data" / "sample_pastificio.xlsx"

needs_graphviz = pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz not installed")


def run_pasta(*args: str) -> subprocess.CompletedProcess:
    """Run "python -m pasta <args>" in a separate process and return its result."""
    # *args: la funzione accetta un numero QUALSIASI di argomenti, raccolti in una tupla
    # (come i parametri variadici "..." in C++). run_pasta("--config", "x.toml").
    #
    # SUBPROCESS (libreria standard) lancia un altro programma, come std::system/popen in C++.
    # - sys.executable = il percorso del Python che sta eseguendo i test (quello del .venv):
    #   così il programma gira con le stesse librerie;
    # - capture_output=True: cattura ciò che il programma stampa (stdout e stderr);
    # - text=True, encoding="utf-8": l'output arriva come testo e non come bytes;
    # - env: le variabili d'ambiente del nuovo processo. PYTHONIOENCODING=utf-8 obbliga il
    #   programma a stampare in UTF-8: sul terminale Windows la codifica predefinita è un'altra
    #   e gli accenti ("Système") arriverebbero storpiati.
    #   {**os.environ, ...} = una copia delle variabili attuali con una in più.
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

    assert result.returncode == 0, result.stderr  # se fallisce, pytest mostra l'errore
    # sorted(...) restituisce una lista ORDINATA; .glob("*") = tutti i file della cartella.
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
    assert "Traceback" not in result.stderr  # un messaggio chiaro, non la traccia di Python
    assert not (tmp_path / "out").exists()


def test_help_works() -> None:
    result = run_pasta("--help")

    assert result.returncode == 0
    assert "--config" in result.stdout
