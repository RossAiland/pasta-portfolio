"""Tests for pasta.loader."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from pasta.loader import LoadError, load_excel

# Il file di esempio vero: tests/ -> cartella del progetto -> data/
SAMPLE_FILE = Path(__file__).resolve().parent.parent / "data" / "sample_pastificio.xlsx"

START = date(2026, 1, 1)
END = date(2100, 12, 31)


# Per i casi particolari non usiamo il file di esempio: costruiamo al volo un Excel MINIMO
# (una riga per foglio) e poi cambiamo solo la parte che ci interessa. Così ogni test
# mostra chiaramente cosa sta verificando.
def minimal_sheets() -> dict[str, pd.DataFrame]:
    """Return the smallest valid content: one row per sheet."""
    return {
        "Noeuds": pd.DataFrame([{"Id": "A", "Actif": True, "DateDebut": START, "DateFin": END}]),
        "Liens": pd.DataFrame(
            [{"Source": "A", "Cible": "A", "Actif": True, "DateDebut": START, "DateFin": END}]
        ),
        "Projets": pd.DataFrame([{"Id": "P", "DateDebut": START, "DateFin": END}]),
        "Parametres": pd.DataFrame([{"Parametre": "DateReference", "Valeur": date(2026, 10, 8)}]),
    }


def write_excel(path: Path, sheets: dict[str, pd.DataFrame]) -> Path:
    """Write one Excel sheet per table and return the path."""
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for name, table in sheets.items():
            table.to_excel(writer, sheet_name=name, index=False)
    return path


def test_sample_file_is_read() -> None:
    data = load_excel(SAMPLE_FILE)

    assert len(data.nodes) == 10
    assert len(data.links) == 12
    assert len(data.projects) == 1
    assert data.parameters["DateReference"] == date(2026, 10, 8)


def test_dates_become_date_objects(tmp_path: Path) -> None:
    data = load_excel(write_excel(tmp_path / "in.xlsx", minimal_sheets()))

    value = data.nodes["DateDebut"].iloc[0]  # .iloc[0] = il valore della PRIMA riga
    # type(value) is date: controlla che sia proprio una date e non un Timestamp/datetime
    # (isinstance non basterebbe: un datetime È anche una date, per ereditarietà).
    assert type(value) is date
    assert value == START
    assert type(data.parameters["DateReference"]) is date


def test_invalid_date_becomes_empty(tmp_path: Path) -> None:
    sheets = minimal_sheets()
    # .loc[riga, colonna] = valore: scrive in una cella precisa (riga con indice 0).
    sheets["Noeuds"].loc[0, "DateFin"] = "not a date"

    data = load_excel(write_excel(tmp_path / "in.xlsx", sheets))

    assert pd.isna(data.nodes.loc[0, "DateFin"])


def test_empty_rows_are_removed_and_row_numbers_kept(tmp_path: Path) -> None:
    sheets = minimal_sheets()
    # Tre righe: A, una riga tutta vuota (None in ogni colonna), B.
    empty = {"Id": None, "Actif": None, "DateDebut": None, "DateFin": None}
    b_row = {"Id": "B", "Actif": True, "DateDebut": START, "DateFin": END}
    sheets["Noeuds"] = pd.DataFrame(
        [{"Id": "A", "Actif": True, "DateDebut": START, "DateFin": END}, empty, b_row]
    )

    data = load_excel(write_excel(tmp_path / "in.xlsx", sheets))

    assert list(data.nodes["Id"]) == ["A", "B"]
    # B conserva l'indice 2 (riga Excel 4): servirà per i messaggi di errore.
    assert list(data.nodes.index) == [0, 2]


def test_row_with_only_actif_is_kept(tmp_path: Path) -> None:
    # Regola "A": una riga con solo Actif compilato NON è vuota. Il loader la tiene, e sarà
    # validation.py a segnalare Id e date mancanti.
    sheets = minimal_sheets()
    only_actif = {"Id": None, "Actif": True, "DateDebut": None, "DateFin": None}
    sheets["Noeuds"] = pd.DataFrame(
        [{"Id": "A", "Actif": True, "DateDebut": START, "DateFin": END}, only_actif]
    )

    data = load_excel(write_excel(tmp_path / "in.xlsx", sheets))

    assert len(data.nodes) == 2
    assert pd.isna(data.nodes.loc[1, "Id"])


def test_actif_values_are_true_or_false(tmp_path: Path) -> None:
    sheets = minimal_sheets()
    # Con una cella vuota nella colonna, pandas legge True/False come 1.0/0.0:
    # il loader deve riportarli a True/False.
    sheets["Noeuds"] = pd.DataFrame(
        [
            {"Id": "A", "Actif": True, "DateDebut": START, "DateFin": END},
            {"Id": "B", "Actif": False, "DateDebut": START, "DateFin": END},
            {"Id": "C", "Actif": None, "DateDebut": START, "DateFin": END},
        ]
    )

    data = load_excel(write_excel(tmp_path / "in.xlsx", sheets))

    actif = data.nodes["Actif"]
    # "is True" e non "== True": deve essere proprio il booleano, non 1.0.
    assert actif.iloc[0] is True
    assert actif.iloc[1] is False


def test_empty_actif_is_not_guessed(tmp_path: Path) -> None:
    # Actif vuoto in una riga piena = errore di compilazione: il loader NON deve inventare
    # un valore. Resta vuoto, e validation.py fermerà il programma.
    sheets = minimal_sheets()
    # NON si può scrivere sheets["Noeuds"].loc[0, "Actif"] = None: la colonna ha dtype bool,
    # e pandas 3 vieta di metterci un valore vuoto (TypeError "Invalid value 'nan' for dtype
    # 'bool'"; pandas 2 cambiava il dtype da solo con un avviso). Quindi creiamo la tabella
    # già con la cella vuota.
    sheets["Noeuds"] = pd.DataFrame(
        [{"Id": "A", "Actif": None, "DateDebut": START, "DateFin": END}]
    )

    data = load_excel(write_excel(tmp_path / "in.xlsx", sheets))

    assert pd.isna(data.nodes.loc[0, "Actif"])


def test_missing_sheet_is_rejected(tmp_path: Path) -> None:
    sheets = minimal_sheets()
    del sheets["Liens"]  # "del" toglie una chiave dal dizionario

    with pytest.raises(LoadError, match="Liens"):
        load_excel(write_excel(tmp_path / "in.xlsx", sheets))


def test_missing_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(LoadError, match="not found"):
        load_excel(tmp_path / "does_not_exist.xlsx")
