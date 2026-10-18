"""Command line entry point: python -m pasta [--config FILE]."""

# COME FUNZIONA "python -m pasta": Python cerca nel package "pasta" un file chiamato
# __main__.py e lo esegue. È il PUNTO DI INGRESSO del programma (come il file con
# "int main()" in C++).
#
# DUE FUNZIONI SEPARATE:
# - run(config_path): fa il lavoro vero (legge, valida, disegna) e restituisce i file scritti.
#   Se qualcosa va storto SOLLEVA un'eccezione: è facile da testare.
# - main(argv): lo strato che parla con l'utente. Legge gli argomenti, chiama run, CATTURA
#   gli errori "previsti" (config sbagliato, Excel mancante, dati non validi, Graphviz non
#   installato) e stampa un messaggio chiaro invece della traccia illeggibile di Python.
#   Restituisce il CODICE DI USCITA: 0 = tutto bene, 1 = errore (come "return 1" da main()
#   in C++; script e altri programmi lo usano per sapere se è andata bene).
# Gli errori IMPREVISTI (bug del programma) non vengono catturati: lì la traccia completa
# serve proprio a capire cosa è successo.

import argparse
import sys
from datetime import date
from pathlib import Path

import graphviz

from pasta.config import ConfigError, load_config
from pasta.loader import LoadError, load_excel
from pasta.model import build_graph
from pasta.render_graphviz import render_svg
from pasta.timeline import compare, take_snapshot
from pasta.validation import DataValidationError, validate

DEFAULT_CONFIG = Path("config.toml")

# TUPLA DI ECCEZIONI: "except (A, B, C)" cattura uno qualsiasi di questi tipi, come più
# blocchi catch in C++ che fanno la stessa cosa.
# graphviz.ExecutableNotFound arriva se il programma Graphviz (dot.exe) non è installato.
EXPECTED_ERRORS = (ConfigError, LoadError, DataValidationError, graphviz.ExecutableNotFound)


def main(argv: list[str] | None = None) -> int:
    """Run the program from the command line and return the exit code."""
    args = _parse_args(argv)
    try:
        written = run(args.config)
    except EXPECTED_ERRORS as error:
        # file=sys.stderr: gli errori vanno sullo "standard error", non sullo standard output
        # (come std::cerr invece di std::cout in C++).
        print(f"Error: {error}", file=sys.stderr)
        return 1
    for path in written:
        print(f"Written: {path}")
    return 0


def run(config_path: Path) -> list[Path]:
    """Read the configuration and the Excel file, check them, draw the graph(s)."""
    config = load_config(config_path)
    data = load_excel(config.input_file)
    validate(data)  # si ferma qui (DataValidationError) se l'Excel ha errori

    # 1. Il grafo a una data.
    # "a or b": la data del config, oppure (se è None) DateReference del foglio Parametres.
    day = config.snapshot_date or _date_reference(data.parameters)
    graph = build_graph(take_snapshot(data, day), data.parameters)
    # Il nome del file contiene la data in formato ANNO-MESE-GIORNO: così, in ordine
    # alfabetico, i file risultano anche in ordine di data.
    written = [render_svg(graph, config.output_dir / f"snapshot_{day:%Y-%m-%d}.svg")]

    # 2. Il confronto tra due date, solo se il config ha la sezione [compare].
    #    config.py garantisce che before e after ci sono entrambe o mancano entrambe.
    if config.compare_before and config.compare_after:
        before, after = config.compare_before, config.compare_after
        comparison = build_graph(compare(data, before, after), data.parameters)
        name = f"compare_{before:%Y-%m-%d}_{after:%Y-%m-%d}.svg"
        written.append(render_svg(comparison, config.output_dir / name))
    return written


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
    # ARGPARSE (libreria standard) legge gli argomenti della riga di comando, controlla che
    # siano giusti e genera da solo l'aiuto: "python -m pasta --help".
    # In C++ dovresti leggere argc/argv a mano.
    parser = argparse.ArgumentParser(
        prog="python -m pasta",
        description="Draw a company's processes, systems and data flows from an Excel file.",
    )
    # type=Path: il testo scritto dall'utente viene convertito subito in un Path.
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"configuration file (default: {DEFAULT_CONFIG})",
    )
    # argv=None: argparse legge i VERI argomenti del terminale (sys.argv). Nei test invece
    # passiamo una lista, es. ["--config", "x.toml"], senza bisogno di un terminale.
    return parser.parse_args(argv)


# Come nel generatore dei dati: questo blocco gira solo se il file viene ESEGUITO
# (python -m pasta), non se viene importato (es. dai test).
# sys.exit(codice) termina il programma restituendo il codice di uscita al terminale.
if __name__ == "__main__":
    sys.exit(main())
