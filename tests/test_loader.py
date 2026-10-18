"""Tests for pasta.loader."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from pasta.loader import LoadError, load_excel

# The real sample file: tests/ -> project folder -> data/
SAMPLE_FILE = Path(__file__).resolve().parent.parent / "data" / "sample_pastificio.xlsx"

START = date(2026, 1, 1)
END = date(2100, 12, 31)


# For special cases we do not use the sample file: we build a MINIMAL Excel file on the fly
# (one row per sheet) and then change only the part we care about. This way each test shows
# clearly what it is checking.
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

    value = data.nodes["DateDebut"].iloc[0]  # .iloc[0] = the value of the FIRST row
    # type(value) is date: checks that it really is a date and not a Timestamp/datetime
    # (isinstance would not be enough: a datetime IS also a date, by inheritance).
    assert type(value) is date
    assert value == START
    assert type(data.parameters["DateReference"]) is date


def test_invalid_date_becomes_empty(tmp_path: Path) -> None:
    sheets = minimal_sheets()
    # .loc[row, column] = value: writes into one specific cell (the row with index 0).
    sheets["Noeuds"].loc[0, "DateFin"] = "not a date"

    data = load_excel(write_excel(tmp_path / "in.xlsx", sheets))

    assert pd.isna(data.nodes.loc[0, "DateFin"])


def test_empty_rows_are_removed_and_row_numbers_kept(tmp_path: Path) -> None:
    sheets = minimal_sheets()
    # Three rows: A, a completely empty row (None in every column), B.
    empty = {"Id": None, "Actif": None, "DateDebut": None, "DateFin": None}
    b_row = {"Id": "B", "Actif": True, "DateDebut": START, "DateFin": END}
    sheets["Noeuds"] = pd.DataFrame(
        [{"Id": "A", "Actif": True, "DateDebut": START, "DateFin": END}, empty, b_row]
    )

    data = load_excel(write_excel(tmp_path / "in.xlsx", sheets))

    assert list(data.nodes["Id"]) == ["A", "B"]
    # B keeps index 2 (Excel row 4): needed for the error messages.
    assert list(data.nodes.index) == [0, 2]


def test_row_with_only_actif_is_kept(tmp_path: Path) -> None:
    # Rule "A": a row with only Actif filled in is NOT empty. The loader keeps it, and
    # validation.py will report the missing Id and dates.
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
    # With an empty cell in the column, pandas reads True/False as 1.0/0.0:
    # the loader must turn them back into True/False.
    sheets["Noeuds"] = pd.DataFrame(
        [
            {"Id": "A", "Actif": True, "DateDebut": START, "DateFin": END},
            {"Id": "B", "Actif": False, "DateDebut": START, "DateFin": END},
            {"Id": "C", "Actif": None, "DateDebut": START, "DateFin": END},
        ]
    )

    data = load_excel(write_excel(tmp_path / "in.xlsx", sheets))

    actif = data.nodes["Actif"]
    # "is True" rather than "== True": it must really be the boolean, not 1.0.
    assert actif.iloc[0] is True
    assert actif.iloc[1] is False


def test_empty_actif_is_not_guessed(tmp_path: Path) -> None:
    # An empty Actif in a filled row = a data entry mistake: the loader must NOT invent a
    # value. It stays empty, and validation.py will stop the program.
    sheets = minimal_sheets()
    # You CANNOT write sheets["Noeuds"].loc[0, "Actif"] = None: the column has dtype bool,
    # and pandas 3 forbids putting an empty value in it (TypeError "Invalid value 'nan' for
    # dtype 'bool'"; pandas 2 changed the dtype by itself with a warning). So the table is
    # created with the empty cell already in it.
    sheets["Noeuds"] = pd.DataFrame(
        [{"Id": "A", "Actif": None, "DateDebut": START, "DateFin": END}]
    )

    data = load_excel(write_excel(tmp_path / "in.xlsx", sheets))

    assert pd.isna(data.nodes.loc[0, "Actif"])


def test_missing_sheet_is_rejected(tmp_path: Path) -> None:
    sheets = minimal_sheets()
    del sheets["Liens"]  # "del" removes a key from the dictionary

    with pytest.raises(LoadError, match="Liens"):
        load_excel(write_excel(tmp_path / "in.xlsx", sheets))


def test_missing_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(LoadError, match="not found"):
        load_excel(tmp_path / "does_not_exist.xlsx")
