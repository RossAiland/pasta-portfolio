"""Tests for pasta.config."""

# HOW PYTEST FINDS THE TESTS: in the tests/ folder (set in pyproject.toml) it looks for files
# named test_*.py and, inside them, for functions named test_*. They do not need to be
# registered anywhere: the name is enough. Run them with "pytest" from the terminal or from
# VSCode's Testing panel (the flask icon).

from datetime import date
from pathlib import Path

import pytest

# Thanks to "pip install -e ." the pasta package can be imported from here like anywhere else.
from pasta.config import ConfigError, load_config

# A complete and correct config, used by several tests.
# Multi-line string: with """...""" you can break lines inside the string.
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
    # write_text opens, writes and closes the file in one line.
    path = folder / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path


# tmp_path FIXTURE: just write a parameter with this name and pytest passes a NEW, EMPTY
# temporary folder, different for every test. This way tests do not interfere with each other
# and do not litter the project. (In C++ with GoogleTest it would be a fixture's SetUp().)
def test_valid_config_is_read(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path, VALID))

    # ASSERT: if the condition is false the test fails, and pytest shows the two values
    # compared (no need for ASSERT_EQ as in GoogleTest: the normal == is enough).
    # How to read a FAILURE: the line with ">" is the assert that failed; the lines with "E"
    # show the real values, e.g. "assert date(2026, 10, 8) == date(2026, 8, 10)".
    # At the end, "FAILED file::test_name" sums up which tests failed.
    # A test is useful only if it FAILS when the code is wrong: when you write one, break the
    # code on purpose and check that the test turns red.
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


# PYTEST.RAISES checks that an error IS raised: the test passes only if a ConfigError comes
# out of the "with" block. match="..." also checks that the message contains that text
# (it is a regex: beware of special characters such as [ ]).
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
