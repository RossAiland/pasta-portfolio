"""Tests for pasta.validation."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from pasta.loader import InputData, load_excel
from pasta.validation import DataValidationError, find_errors, validate

SAMPLE_FILE = Path(__file__).resolve().parent.parent / "data" / "sample_pastificio.xlsx"

# Rows of the sample file used in the tests (pandas index -> Excel row = index + 2):
#   Noeuds: 1 = MP_SALES (row 3), 4 = P_INVOICE (row 6), 5 = MILL (row 7),
#           7 = SHEETS (row 9), 8 = SHOP (row 10)
#   Liens:  4 = P_PLAN -> MILL (row 6)


# CUSTOM FIXTURE: @pytest.fixture turns a function into a fixture, like tmp_path but written
# by us. Every test with a parameter called "sample" receives a NEW object returned by this
# function: each test can break the data as it likes without disturbing the others.
# (In GoogleTest it would be the fixture's SetUp().)
@pytest.fixture
def sample() -> InputData:
    data = load_excel(SAMPLE_FILE)
    # Actif is a column of dtype bool, and pandas 3 forbids putting non-boolean values in it
    # (None, text). It is turned into "object" so the tests can break it.
    data.nodes["Actif"] = data.nodes["Actif"].astype(object)
    return data


def test_sample_file_has_no_errors() -> None:
    # Here the file is used as it is, without the fixture: the Actif column keeps dtype bool
    # (numpy.bool_ values). So this test also checks that numpy.bool_ values are accepted.
    assert find_errors(load_excel(SAMPLE_FILE)) == []


def test_missing_column(sample: InputData) -> None:
    # drop(columns=[...]) returns a NEW table without that column.
    sample.nodes = sample.nodes.drop(columns=["Libelle"])

    assert "Noeuds: column 'Libelle' is missing" in find_errors(sample)


def test_empty_id(sample: InputData) -> None:
    sample.nodes.loc[1, "Id"] = None

    assert "Noeuds, row 3: Id is empty" in find_errors(sample)


def test_actif_must_be_true_or_false(sample: InputData) -> None:
    sample.nodes.loc[5, "Actif"] = None
    sample.nodes.loc[7, "Actif"] = "oui"

    # == on two lists: true if they have the same elements in the same order.
    assert find_errors(sample) == [
        "Noeuds, row 7: Actif must be True or False (found: empty)",
        "Noeuds, row 9: Actif must be True or False (found: 'oui')",
    ]


def test_duplicate_ids_are_all_reported(sample: InputData) -> None:
    sample.nodes.loc[4, "Id"] = "MILL"  # P_INVOICE becomes a second MILL

    errors = find_errors(sample)

    # BOTH rows with the same Id are reported.
    assert "Noeuds, row 6: Id 'MILL' is used by more than one row" in errors
    assert "Noeuds, row 7: Id 'MILL' is used by more than one row" in errors


def test_invalid_date(sample: InputData) -> None:
    sample.nodes.loc[7, "DateFin"] = pd.NaT  # what the loader turns an invalid date into

    assert find_errors(sample) == ["Noeuds, row 9: DateFin is empty or not a valid date"]


def test_date_fin_before_date_debut(sample: InputData) -> None:
    sample.nodes.loc[8, "DateFin"] = date(2026, 1, 1)  # SHOP starts on 2027-03-01

    assert find_errors(sample) == [
        "Noeuds, row 10: DateFin 2026-01-01 is before DateDebut 2027-03-01"
    ]


def test_link_to_unknown_node(sample: InputData) -> None:
    sample.links.loc[4, "Cible"] = "MIILL"  # typo

    assert find_errors(sample) == ["Liens, row 6: Cible 'MIILL' is not an Id in Noeuds"]


def test_unknown_project(sample: InputData) -> None:
    sample.nodes.loc[8, "Projet"] = "PRJ_SHOPP"

    assert find_errors(sample) == ["Noeuds, row 10: Projet 'PRJ_SHOPP' is not an Id in Projets"]


def test_empty_project_is_fine(sample: InputData) -> None:
    sample.nodes.loc[8, "Projet"] = None  # no project: not an error

    assert find_errors(sample) == []


def test_errors_are_sorted_by_sheet_and_row(sample: InputData) -> None:
    sample.links.loc[4, "Cible"] = "MIILL"  # Liens, row 6
    sample.nodes.loc[8, "Projet"] = "PRJ_SHOPP"  # Noeuds, row 10
    sample.nodes.loc[5, "Actif"] = None  # Noeuds, row 7

    errors = find_errors(sample)

    # First Noeuds then Liens; within Noeuds row 7 before row 10 (as numbers, not as text:
    # as text "row 10" would come before "row 7").
    # error.split(":") splits the string at ":" and returns a list of pieces; [0] takes the
    # first piece, i.e. "Noeuds, row 7". The list comprehension does it for every error.
    assert [error.split(":")[0] for error in errors] == [
        "Noeuds, row 7",
        "Noeuds, row 10",
        "Liens, row 6",
    ]


def test_validate_raises_with_the_full_list(sample: InputData) -> None:
    sample.nodes.loc[5, "Actif"] = None
    sample.links.loc[4, "Cible"] = "MIILL"

    # "as caught": after the block, caught.value is the exception that was raised.
    with pytest.raises(DataValidationError) as caught:
        validate(sample)

    assert len(caught.value.errors) == 2
    assert "2 error(s)" in str(caught.value)


def test_validate_accepts_correct_data() -> None:
    validate(load_excel(SAMPLE_FILE))  # no exception = test passed
