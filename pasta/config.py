"""Read the configuration file (config.toml)."""

# tomllib è nella libreria standard da Python 3.11: legge i file TOML senza installare nulla.
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path


# Eccezione personalizzata: basta derivare da Exception, il corpo può essere solo la docstring.
# Il nome dice già cosa è andato storto, e chi chiama può fare "except ConfigError"
# senza intercettare per sbaglio altri tipi di errore.
class ConfigError(Exception):
    """The configuration file is missing, unreadable or has a wrong value."""


# DATACLASS = la "struct" di Python. In C++ sarebbe:
#     struct Config {
#         std::filesystem::path input_file;
#         std::filesystem::path output_dir;
#         std::optional<Date> snapshot_date = std::nullopt;  ...
#     };
# @dataclass è un DECORATORE: una riga sopra la classe che la "arricchisce". Dall'elenco dei
# campi Python genera da solo il costruttore Config(input_file=..., ...), il confronto == e la
# stampa leggibile Config(input_file=WindowsPath(...), ...). Senza @dataclass andrebbero scritti
# a mano __init__, __eq__ e __repr__.
# frozen=True rende l'oggetto IMMUTABILE dopo la creazione (come se tutti i campi fossero const):
# "config.output_dir = ..." darebbe errore. Una configurazione non deve cambiare
# durante l'esecuzione.
@dataclass(frozen=True)
class Config:
    """Everything the program needs to know before reading the Excel file."""

    # TYPE HINTS: "nome: tipo". Si leggono come in C++, ma il tipo sta DOPO il nome.
    # "date | None" = una data oppure niente, l'equivalente di std::optional<date>.
    # ATTENZIONE: Python NON controlla i type hints quando esegue il codice. Servono a VSCode
    # (Pylance) per suggerire i metodi e sottolineare gli errori mentre scrivi. Per questo più
    # sotto controlliamo comunque i valori a mano con isinstance().
    input_file: Path
    output_dir: Path
    snapshot_date: date | None = None  # None: use DateReference from the Excel file
    compare_before: date | None = None  # None: no comparison
    compare_after: date | None = None


# "path: Path" = mi aspetto un Path; "-> Config" = restituisco un Config.
def load_config(path: Path) -> Config:
    """Read a TOML configuration file and check its values."""
    try:
        # tomllib vuole il file aperto in modalità BINARIA ("rb"): così lo decodifica lui,
        # sempre in UTF-8, qualunque sia la codifica predefinita di Windows (accenti salvi).
        # "with" chiude il file anche in caso di errore (come RAII in C++).
        with open(path, "rb") as file:
            # Il risultato è un dizionario. Una sezione [compare] diventa un dizionario
            # annidato: data["compare"]["after"]. Le date SENZA virgolette (2026-10-08)
            # diventano subito oggetti datetime.date; CON le virgolette sarebbero stringhe.
            data = tomllib.load(file)
    except FileNotFoundError:
        # "from None": dentro un except Python mostrerebbe ENTRAMBI gli errori (l'originale e
        # il nostro, con "During handling of the above exception, another exception occurred").
        # from None nasconde l'originale perché il nostro messaggio è già completo.
        # Per tenere la catena si scrive invece "from error".
        raise ConfigError(f"Configuration file not found: {path}") from None
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path.name} is not valid TOML: {error}") from None

    # I percorsi relativi partono dalla cartella del file di config, non da dove si lancia
    # il programma: stessa idea di __file__ nel generatore dei dati.
    folder = path.parent
    # .get(chiave, default) restituisce il default se la chiave manca (data["compare"]
    # darebbe invece KeyError). Così la sezione [compare] può mancare.
    compare = data.get("compare", {})
    config = Config(
        input_file=folder / _required_text(data, "input_file"),
        output_dir=folder / _required_text(data, "output_dir"),
        snapshot_date=_optional_date(data.get("snapshot_date"), "snapshot_date"),
        compare_before=_optional_date(compare.get("before"), "compare.before"),
        compare_after=_optional_date(compare.get("after"), "compare.after"),
    )

    # Confronto tra due booleani con != : funziona da XOR. È vero se ESATTAMENTE una delle
    # due date manca, cioè se ne è stata scritta una sola.
    # "is None" e non "== None": None è un oggetto unico e "is" controlla l'identità
    # (come confrontare un puntatore con nullptr). Ruff segnalerebbe "== None".
    if (config.compare_before is None) != (config.compare_after is None):
        raise ConfigError("[compare] needs both 'before' and 'after'")
    if config.compare_before and config.compare_after <= config.compare_before:
        raise ConfigError("[compare] 'after' must be later than 'before'")
    return config


# Il TRATTINO BASSO iniziale (_required_text) è la convenzione per "funzione interna al
# modulo, non usarla da fuori": come private, o una funzione static in un .cpp.
# Python non lo impone, ma VSCode e chi legge lo capiscono.
def _required_text(data: dict, key: str) -> str:
    """Return data[key], or raise ConfigError if it is missing or not a string."""
    value = data.get(key)
    if not isinstance(value, str) or value == "":
        raise ConfigError(f"'{key}' is required and must be text in quotes")
    return value


# "value: object" = qualsiasi cosa: dal TOML può arrivare di tutto.
def _optional_date(value: object, name: str) -> date | None:
    """Return the value if it is a date (or None), otherwise raise ConfigError."""
    if value is None or isinstance(value, date):
        return value
    # {value!r} nella f-string stampa la RAPPRESENTAZIONE dell'oggetto ('2026-10-08' con le
    # virgolette) invece del testo: si vede subito che è una stringa e non una data.
    raise ConfigError(f"'{name}' must be a date like 2026-10-08, without quotes (got {value!r})")
