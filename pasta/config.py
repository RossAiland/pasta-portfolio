"""Read the configuration file (config.toml)."""

# tomllib is in the standard library since Python 3.11: it reads TOML files, nothing to install.
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path


# Custom exception: deriving from Exception is enough, the body can be just the docstring.
# The name already says what went wrong, and callers can write "except ConfigError"
# without catching other kinds of errors by mistake.
class ConfigError(Exception):
    """The configuration file is missing, unreadable or has a wrong value."""


# DATACLASS = Python's "struct". In C++ it would be:
#     struct Config {
#         std::filesystem::path input_file;
#         std::filesystem::path output_dir;
#         std::optional<Date> snapshot_date = std::nullopt;  ...
#     };
# @dataclass is a DECORATOR: a line above the class that "enriches" it. From the list of
# fields Python generates the constructor Config(input_file=..., ...), the == comparison and
# a readable printout Config(input_file=WindowsPath(...), ...). Without @dataclass we would
# have to write __init__, __eq__ and __repr__ by hand.
# frozen=True makes the object IMMUTABLE after creation (as if every field were const):
# "config.output_dir = ..." raises an error. A configuration must not change while the
# program runs.
@dataclass(frozen=True)
class Config:
    """Everything the program needs to know before reading the Excel file."""

    # TYPE HINTS: "name: type". They read like C++, but the type comes AFTER the name.
    # "date | None" = a date or nothing, the equivalent of std::optional<date>.
    # WARNING: Python does NOT check type hints when it runs the code. They are for VSCode
    # (Pylance), which uses them to suggest methods and underline mistakes while you type.
    # That is why the values are still checked by hand with isinstance() further down.
    input_file: Path
    output_dir: Path
    snapshot_date: date | None = None  # None: use DateReference from the Excel file
    compare_before: date | None = None  # None: no comparison
    compare_after: date | None = None


# "path: Path" = I expect a Path; "-> Config" = I return a Config.
def load_config(path: Path) -> Config:
    """Read a TOML configuration file and check its values."""
    try:
        # tomllib wants the file opened in BINARY mode ("rb"): it then decodes it itself,
        # always as UTF-8, whatever the Windows default encoding is (accents stay safe).
        # "with" closes the file even if an error happens (like RAII in C++).
        with open(path, "rb") as file:
            # The result is a dictionary. A [compare] section becomes a nested dictionary:
            # data["compare"]["after"]. Dates WITHOUT quotes (2026-10-08) become
            # datetime.date objects right away; WITH quotes they would be strings.
            data = tomllib.load(file)
    except FileNotFoundError:
        # "from None": inside an except block Python would show BOTH errors (the original one
        # and ours, with "During handling of the above exception, another exception
        # occurred"). from None hides the original, because our message is already complete.
        # To keep the chain you would write "from error" instead.
        raise ConfigError(f"Configuration file not found: {path}") from None
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path.name} is not valid TOML: {error}") from None

    # Relative paths start from the folder of the config file, not from where the program
    # is launched: same idea as __file__ in the sample data generator.
    folder = path.parent
    # .get(key, default) returns the default if the key is missing (data["compare"] would
    # raise KeyError instead). This way the [compare] section is optional.
    compare = data.get("compare", {})
    config = Config(
        input_file=folder / _required_text(data, "input_file"),
        output_dir=folder / _required_text(data, "output_dir"),
        snapshot_date=_optional_date(data.get("snapshot_date"), "snapshot_date"),
        compare_before=_optional_date(compare.get("before"), "compare.before"),
        compare_after=_optional_date(compare.get("after"), "compare.after"),
    )

    # Comparing two booleans with != works as XOR: it is true if EXACTLY one of the two
    # dates is missing, i.e. only one was written.
    # "is None" rather than "== None": None is a unique object and "is" checks identity
    # (like comparing a pointer with nullptr). Ruff would flag "== None".
    if (config.compare_before is None) != (config.compare_after is None):
        raise ConfigError("[compare] needs both 'before' and 'after'")
    if config.compare_before and config.compare_after <= config.compare_before:
        raise ConfigError("[compare] 'after' must be later than 'before'")
    return config


# The leading UNDERSCORE (_required_text) is the convention for "internal to this module,
# don't use it from outside": like private, or a static function in a .cpp file.
# Python does not enforce it, but VSCode and readers understand it.
def _required_text(data: dict, key: str) -> str:
    """Return data[key], or raise ConfigError if it is missing or not a string."""
    value = data.get(key)
    if not isinstance(value, str) or value == "":
        raise ConfigError(f"'{key}' is required and must be text in quotes")
    return value


# "value: object" = anything: any kind of value can come from the TOML file.
def _optional_date(value: object, name: str) -> date | None:
    """Return the value if it is a date (or None), otherwise raise ConfigError."""
    if value is None or isinstance(value, date):
        return value
    # {value!r} in an f-string prints the REPRESENTATION of the object ('2026-10-08' with
    # quotes) instead of its text: it shows at once that it is a string and not a date.
    raise ConfigError(f"'{name}' must be a date like 2026-10-08, without quotes (got {value!r})")
