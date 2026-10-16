"""Tests for pasta.config."""

# COME PYTEST TROVA I TEST: cerca nella cartella tests/ (impostata in pyproject.toml) i file
# che si chiamano test_*.py e, dentro, le funzioni che si chiamano test_*. Non serve
# registrarle da nessuna parte: basta il nome. Si lanciano con "pytest" dal terminale
# oppure dal pannello Testing di VSCode (icona della provetta).

from datetime import date
from pathlib import Path

import pytest

# Grazie a "pip install -e ." il package pasta si importa da qui come da qualsiasi altro posto.
from pasta.config import ConfigError, load_config

# Un config completo e corretto, usato da più test.
# Stringa su più righe: con """...""" si può andare a capo dentro la stringa.
VALID = """
input_file = "data/file.xlsx"
output_dir = "out"
snapshot_date = 2026-10-08

[compare]
before = 2026-10-08
after = 2027-06-01
"""


def write_config(folder: Path, text: str) -> Path:
    """Write text into folder/config.toml and return its path."""
    # write_text apre, scrive e chiude il file in una riga sola.
    path = folder / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path


# FIXTURE tmp_path: basta scrivere un parametro con questo nome e pytest passa da solo una
# cartella temporanea NUOVA e VUOTA, diversa per ogni test. Così i test non si disturbano a
# vicenda e non sporcano il progetto. (In C++ con GoogleTest sarebbe il SetUp() di una fixture.)
def test_valid_config_is_read(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path, VALID))

    # ASSERT: se la condizione è falsa il test fallisce, e pytest mostra i due valori
    # confrontati (non serve ASSERT_EQ come in GoogleTest: basta il normale ==).
    # Come si legge un FALLIMENTO: la riga con ">" è l'assert che ha fallito; le righe con
    # "E" mostrano i valori veri, es. "assert date(2026, 10, 8) == date(2026, 8, 10)".
    # In fondo, "FAILED file::nome_test" riassume quali test sono falliti.
    # Un test è utile solo se FALLISCE quando il codice è sbagliato: quando ne scrivi uno,
    # prova a rompere apposta il codice e controlla che diventi rosso.
    assert config.snapshot_date == date(2026, 10, 8)
    assert config.compare_before == date(2026, 10, 8)
    assert config.compare_after == date(2027, 6, 1)


def test_paths_start_from_the_config_folder(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path, VALID))

    assert config.input_file == tmp_path / "data" / "file.xlsx"
    assert config.output_dir == tmp_path / "out"


def test_snapshot_date_and_compare_are_optional(tmp_path: Path) -> None:
    text = 'input_file = "a.xlsx"\noutput_dir = "out"\n'

    config = load_config(write_config(tmp_path, text))

    assert config.snapshot_date is None
    assert config.compare_before is None
    assert config.compare_after is None


# PYTEST.RAISES verifica che un errore VENGA sollevato: il test passa solo se dentro il
# blocco "with" arriva un ConfigError. match="..." controlla anche che il messaggio
# contenga quel testo (è una regex: attenzione ai caratteri speciali come [ ]).
def test_missing_config_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "does_not_exist.toml")


def test_missing_input_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="input_file"):
        load_config(write_config(tmp_path, 'output_dir = "out"\n'))


def test_date_in_quotes_is_rejected(tmp_path: Path) -> None:
    text = 'input_file = "a.xlsx"\noutput_dir = "out"\nsnapshot_date = "2026-10-08"\n'

    with pytest.raises(ConfigError, match="without quotes"):
        load_config(write_config(tmp_path, text))


def test_compare_needs_both_dates(tmp_path: Path) -> None:
    text = 'input_file = "a.xlsx"\noutput_dir = "out"\n[compare]\nbefore = 2026-10-08\n'

    with pytest.raises(ConfigError, match="both"):
        load_config(write_config(tmp_path, text))


def test_compare_after_must_be_later(tmp_path: Path) -> None:
    text = """
input_file = "a.xlsx"
output_dir = "out"
[compare]
before = 2027-01-01
after = 2026-01-01
"""

    with pytest.raises(ConfigError, match="later"):
        load_config(write_config(tmp_path, text))
