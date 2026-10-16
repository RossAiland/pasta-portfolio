"""Tests for pasta.validation."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from pasta.loader import InputData, load_excel
from pasta.validation import DataValidationError, find_errors, validate

SAMPLE_FILE = Path(__file__).resolve().parent.parent / "data" / "sample_pastificio.xlsx"

# Righe del file di esempio usate nei test (indice pandas -> riga Excel = indice + 2):
#   Noeuds: 1 = MP_SALES (riga 3), 4 = P_INVOICE (riga 6), 5 = MILL (riga 7),
#           7 = SHEETS (riga 9), 8 = SHOP (riga 10)
#   Liens:  4 = P_PLAN -> MILL (riga 6)


# FIXTURE PERSONALIZZATA: @pytest.fixture trasforma una funzione in una fixture, come
# tmp_path ma scritta da noi. Ogni test che ha un parametro chiamato "sample" riceve un
# oggetto NUOVO restituito da questa funzione: ogni test può rompere i dati come vuole
# senza disturbare gli altri. (In GoogleTest sarebbe il SetUp() della fixture.)
@pytest.fixture
def sample() -> InputData:
    data = load_excel(SAMPLE_FILE)
    # Actif è una colonna di dtype bool, e pandas 3 vieta di metterci valori che non sono
    # booleani (None, testo). La trasformiamo in "object" per poterla rompere nei test.
    data.nodes["Actif"] = data.nodes["Actif"].astype(object)
    return data


def test_sample_file_has_no_errors() -> None:
    # Qui usiamo il file così com'è, senza la fixture: la colonna Actif resta di dtype bool
    # (valori numpy.bool_). Il test verifica quindi anche che i numpy.bool_ siano accettati.
    assert find_errors(load_excel(SAMPLE_FILE)) == []


def test_missing_column(sample: InputData) -> None:
    # drop(columns=[...]) restituisce una NUOVA tabella senza quella colonna.
    sample.nodes = sample.nodes.drop(columns=["Libelle"])

    assert "Noeuds: column 'Libelle' is missing" in find_errors(sample)


def test_empty_id(sample: InputData) -> None:
    sample.nodes.loc[1, "Id"] = None

    assert "Noeuds, row 3: Id is empty" in find_errors(sample)


def test_actif_must_be_true_or_false(sample: InputData) -> None:
    sample.nodes.loc[5, "Actif"] = None
    sample.nodes.loc[7, "Actif"] = "oui"

    # == su due liste: vero se hanno gli stessi elementi nello stesso ordine.
    assert find_errors(sample) == [
        "Noeuds, row 7: Actif must be True or False (found: empty)",
        "Noeuds, row 9: Actif must be True or False (found: 'oui')",
    ]


def test_duplicate_ids_are_all_reported(sample: InputData) -> None:
    sample.nodes.loc[4, "Id"] = "MILL"  # P_INVOICE diventa un secondo MILL

    errors = find_errors(sample)

    # Vengono segnalate ENTRAMBE le righe con lo stesso Id.
    assert "Noeuds, row 6: Id 'MILL' is used by more than one row" in errors
    assert "Noeuds, row 7: Id 'MILL' is used by more than one row" in errors


def test_invalid_date(sample: InputData) -> None:
    sample.nodes.loc[7, "DateFin"] = pd.NaT  # come il loader trasforma una data non valida

    assert find_errors(sample) == ["Noeuds, row 9: DateFin is empty or not a valid date"]


def test_date_fin_before_date_debut(sample: InputData) -> None:
    sample.nodes.loc[8, "DateFin"] = date(2026, 1, 1)  # SHOP inizia il 2027-03-01

    assert find_errors(sample) == [
        "Noeuds, row 10: DateFin 2026-01-01 is before DateDebut 2027-03-01"
    ]


def test_link_to_unknown_node(sample: InputData) -> None:
    sample.links.loc[4, "Cible"] = "MIILL"  # errore di battitura

    assert find_errors(sample) == ["Liens, row 6: Cible 'MIILL' is not an Id in Noeuds"]


def test_unknown_project(sample: InputData) -> None:
    sample.nodes.loc[8, "Projet"] = "PRJ_SHOPP"

    assert find_errors(sample) == ["Noeuds, row 10: Projet 'PRJ_SHOPP' is not an Id in Projets"]


def test_empty_project_is_fine(sample: InputData) -> None:
    sample.nodes.loc[8, "Projet"] = None  # nessun progetto: non è un errore

    assert find_errors(sample) == []


def test_errors_are_sorted_by_sheet_and_row(sample: InputData) -> None:
    sample.links.loc[4, "Cible"] = "MIILL"  # Liens, riga 6
    sample.nodes.loc[8, "Projet"] = "PRJ_SHOPP"  # Noeuds, riga 10
    sample.nodes.loc[5, "Actif"] = None  # Noeuds, riga 7

    errors = find_errors(sample)

    # Prima Noeuds poi Liens; dentro Noeuds la riga 7 prima della 10 (come numeri, non come
    # testo: come testo "row 10" verrebbe prima di "row 7").
    # error.split(":") divide la stringa ai ":" e restituisce una lista di pezzi; [0] prende
    # il primo pezzo, cioè "Noeuds, row 7". La list comprehension lo fa per ogni errore.
    assert [error.split(":")[0] for error in errors] == [
        "Noeuds, row 7",
        "Noeuds, row 10",
        "Liens, row 6",
    ]


def test_validate_raises_with_the_full_list(sample: InputData) -> None:
    sample.nodes.loc[5, "Actif"] = None
    sample.links.loc[4, "Cible"] = "MIILL"

    # "as caught": dopo il blocco, caught.value è l'eccezione sollevata.
    with pytest.raises(DataValidationError) as caught:
        validate(sample)

    assert len(caught.value.errors) == 2
    assert "2 error(s)" in str(caught.value)


def test_validate_accepts_correct_data() -> None:
    validate(load_excel(SAMPLE_FILE))  # nessuna eccezione = test passato
