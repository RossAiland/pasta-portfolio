"""Check the content of the Excel file and report ALL the errors at once."""

from dataclasses import dataclass

import pandas as pd

from pasta.loader import LINKS_SHEET, NODES_SHEET, PROJECTS_SHEET, InputData

# IDEA: instead of stopping at the FIRST error, the whole file is checked and the errors are
# collected in a list. Whoever fixes the Excel file sees the complete list at once, instead
# of fixing, re-running, finding the next error, and so on.
#
# TWO SEPARATE FUNCTIONS:
# - find_errors(data) -> list[str]: FINDS the errors and returns them (easy to test: just
#   check the list);
# - validate(data): calls find_errors and, if the list is not empty, STOPS the program by
#   raising DataValidationError. This is the one the program uses.

# Columns that MUST exist in each sheet and cannot have empty cells.
# (Actif is checked separately: it must be True or False.)
NODE_REQUIRED = ["Id", "Libelle", "TypeElement", "Actif", "DateDebut", "DateFin"]
LINK_REQUIRED = ["Source", "Cible", "Actif", "DateDebut", "DateFin"]
PROJECT_REQUIRED = ["Id"]

# Order of the sheets in the list of errors (the same as in the Excel file).
SHEET_ORDER = {NODES_SHEET: 0, LINKS_SHEET: 1, PROJECTS_SHEET: 2}


class DataValidationError(Exception):
    """The input file has one or more errors; .errors holds the full list."""

    # Unlike ConfigError, this exception has a CONSTRUCTOR (__init__): it receives the list
    # of errors and keeps it in self.errors, so whoever catches it can use it (for example
    # a test can count the errors).
    # "self" is the object itself: like "this" in C++, but it must be written explicitly as
    # the first parameter of every method.
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        # "\n".join(list) joins the strings of the list with a newline between them.
        # Inside join there is a GENERATOR EXPRESSION: like a list comprehension without [ ].
        # It produces the values one at a time instead of building a whole list in memory.
        lines = "\n".join(f"  {error}" for error in errors)
        # super().__init__(...) calls the constructor of the base class (Exception), like
        # ": Exception(message)" in the initializer list of a C++ constructor.
        # The text passed is the message shown when the error is printed.
        super().__init__(f"The input file has {len(errors)} error(s):\n{lines}")


# One error found, with the row number as an INTEGER: if they were plain strings, sorting
# them would put "row 10" before "row 9" (strings are compared character by character).
# Sorting uses the fields, and only at the end is the error turned into text.
@dataclass
class Problem:
    sheet: str
    row: int  # Excel row; 0 = a problem of the whole sheet (e.g. a missing column)
    text: str

    # A METHOD: a function defined inside the class, which receives the object as "self".
    def __str__(self) -> str:
        # __str__ is the "special" method Python calls when the object becomes text
        # (str(problem), print(problem), f"{problem}"). Like overloading operator<< in C++.
        if self.row == 0:
            return f"{self.sheet}: {self.text}"
        return f"{self.sheet}, row {self.row}: {self.text}"


def validate(data: InputData) -> None:
    """Stop the program with DataValidationError if the input data has errors."""
    errors = find_errors(data)
    if errors:
        raise DataValidationError(errors)


def find_errors(data: InputData) -> list[str]:
    """Return the list of all the errors found in the input data (empty if all is fine)."""
    problems: list[Problem] = []  # type hint on a variable: "list of Problem", empty for now

    # If a sheet is missing columns, the other checks on that sheet make no sense (they would
    # raise KeyError): the problem is reported and the sheet is skipped.
    # The _check_* functions receive the "problems" list and FILL it: in Python a list passed
    # to a function is NOT copied (like passing a reference in C++), so what is appended
    # inside the function is visible here too.
    nodes_ok = _check_columns(data.nodes, NODES_SHEET, NODE_REQUIRED, problems)
    links_ok = _check_columns(data.links, LINKS_SHEET, LINK_REQUIRED, problems)
    projects_ok = _check_columns(data.projects, PROJECTS_SHEET, PROJECT_REQUIRED, problems)

    if nodes_ok:
        _check_not_empty(data.nodes, NODES_SHEET, NODE_REQUIRED, problems)
        _check_actif(data.nodes, NODES_SHEET, problems)
        _check_unique_ids(data.nodes, NODES_SHEET, problems)
        _check_date_order(data.nodes, NODES_SHEET, problems)
    if links_ok:
        _check_not_empty(data.links, LINKS_SHEET, LINK_REQUIRED, problems)
        _check_actif(data.links, LINKS_SHEET, problems)
        _check_date_order(data.links, LINKS_SHEET, problems)
    if projects_ok:
        _check_not_empty(data.projects, PROJECTS_SHEET, PROJECT_REQUIRED, problems)
        _check_unique_ids(data.projects, PROJECTS_SHEET, problems)
        _check_date_order(data.projects, PROJECTS_SHEET, problems)

    # Checks across sheets: they need the columns of both.
    if nodes_ok and links_ok:
        for column in ["Source", "Cible"]:
            _check_references(
                data.links, LINKS_SHEET, column, data.nodes["Id"], NODES_SHEET, problems
            )
    if projects_ok:
        project_ids = data.projects["Id"]
        if nodes_ok and "Projet" in data.nodes.columns:
            _check_references(
                data.nodes, NODES_SHEET, "Projet", project_ids, PROJECTS_SHEET, problems
            )
        if links_ok and "Projet" in data.links.columns:
            _check_references(
                data.links, LINKS_SHEET, "Projet", project_ids, PROJECTS_SHEET, problems
            )

    # SORTING by sheet, then by row.
    # key=... tells sort() WHAT to compare. "lambda p: ..." is a one-line anonymous function
    # (like a C++ lambda: [](const Problem& p) { return ...; }).
    # It returns a TUPLE: tuples are compared field by field (first the sheet, then, for the
    # same sheet, the row), like std::tie in C++.
    # sort() is STABLE: two errors on the same row keep the order in which they were found.
    problems.sort(key=lambda p: (SHEET_ORDER[p.sheet], p.row))
    return [str(problem) for problem in problems]


def _excel_row(index: int) -> int:
    """Return the row number shown in Excel for a pandas index."""
    # Excel row = index + 2: +1 because the pandas index starts at 0, +1 for the header row.
    # The loader keeps the original index even after removing empty rows, so the number is
    # the right one.
    return index + 2


def _check_columns(
    table: pd.DataFrame, sheet: str, required: list[str], problems: list[Problem]
) -> bool:
    """Add a problem for each missing column; return True if none is missing."""
    missing = [column for column in required if column not in table.columns]
    for column in missing:
        problems.append(Problem(sheet, 0, f"column '{column}' is missing"))
    # "not missing": True if the list is empty (no missing column).
    return not missing


def _check_not_empty(
    table: pd.DataFrame, sheet: str, columns: list[str], problems: list[Problem]
) -> None:
    """Add a problem for each empty cell in the given columns (Actif excluded)."""
    for column in columns:
        if column == "Actif":
            continue  # checked by _check_actif
        # BOOLEAN MASK: table[column].isna() returns a column of True/False, True where the
        # cell is empty. It is a vectorized operation (no loop over the rows).
        empty = table[column].isna()
        # table.index[mask] = the INDEXES of the rows where the mask is True.
        for index in table.index[empty]:
            # For dates, "empty" also covers "was not a date": the loader turned invalid
            # values into NaT.
            if column.startswith("Date"):
                text = f"{column} is empty or not a valid date"
            else:
                text = f"{column} is empty"
            problems.append(Problem(sheet, _excel_row(index), text))


def _check_actif(table: pd.DataFrame, sheet: str, problems: list[Problem]) -> None:
    """Add a problem for each Actif cell that is not exactly True or False."""
    # pd.api.types.is_bool(v) is true both for Python bools and for numpy.bool_ (the type
    # pandas uses when the column is all booleans). With isinstance(v, bool) the numpy.bool_
    # values would be rejected by mistake.
    # .map(function) applies it to every cell; "~" NEGATES a mask (True <-> False),
    # like "!" in C++ but element by element.
    wrong = ~table["Actif"].map(pd.api.types.is_bool)
    for index in table.index[wrong]:
        value = table.at[index, "Actif"]  # .at[index, column] = the value of ONE cell
        # CONDITIONAL EXPRESSION "a if condition else b": the C++ ternary operator
        # (condition ? a : b), written in a different order.
        # repr(value) gives the representation of the value: 'oui' with quotes, 1.5 without.
        found = "empty" if pd.isna(value) else repr(value)
        text = f"Actif must be True or False (found: {found})"
        problems.append(Problem(sheet, _excel_row(index), text))


def _check_unique_ids(table: pd.DataFrame, sheet: str, problems: list[Problem]) -> None:
    """Add a problem for each row whose Id is also used by another row."""
    # duplicated(keep=False) marks as True ALL the rows whose value appears more than once
    # (with the default keep="first" the first one would stay False and not be reported).
    # "&" combines two masks: True only where BOTH are true (an element-wise "and").
    # Empty Ids are already reported by _check_not_empty, so they are excluded here.
    # When comparisons are combined with & in one line, PARENTHESES are required:
    # & has a higher precedence than comparisons.
    ids = table["Id"]
    duplicated = ids.duplicated(keep=False) & ids.notna()
    for index in table.index[duplicated]:
        text = f"Id '{ids[index]}' is used by more than one row"
        problems.append(Problem(sheet, _excel_row(index), text))


def _check_date_order(table: pd.DataFrame, sheet: str, problems: list[Problem]) -> None:
    """Add a problem for each row whose DateFin is before its DateDebut."""
    if "DateDebut" not in table.columns or "DateFin" not in table.columns:
        return  # in the Projets sheet the dates are optional
    # Only rows with BOTH dates are compared: empty ones are already reported by
    # _check_not_empty, and comparing a date with an empty value makes no sense.
    both = table["DateDebut"].notna() & table["DateFin"].notna()
    # table.loc[mask] = only the rows where the mask is True (a smaller table, which keeps
    # the original indexes).
    dated = table.loc[both]
    wrong = dated["DateFin"] < dated["DateDebut"]
    for index in dated.index[wrong]:
        start, end = dated.at[index, "DateDebut"], dated.at[index, "DateFin"]
        text = f"DateFin {end} is before DateDebut {start}"
        problems.append(Problem(sheet, _excel_row(index), text))


def _check_references(
    table: pd.DataFrame,
    sheet: str,
    column: str,
    valid_ids: pd.Series,
    target_sheet: str,
    problems: list[Problem],
) -> None:
    """Add a problem for each value of table[column] that is not one of valid_ids."""
    # pd.Series = ONE pandas column (a DataFrame is a set of named Series).
    # isin(values): mask that is True where the cell value is among the given values. With
    # "~" we get the ones that are NOT. Empty cells are not a wrong reference (e.g. an empty
    # Projet = no project; an empty Source is already reported by _check_not_empty).
    values = table[column]
    unknown = ~values.isin(valid_ids) & values.notna()
    for index in table.index[unknown]:
        text = f"{column} '{values[index]}' is not an Id in {target_sheet}"
        problems.append(Problem(sheet, _excel_row(index), text))
