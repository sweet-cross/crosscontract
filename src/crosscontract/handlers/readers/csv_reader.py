import io
from pathlib import Path

import pandas as pd

from crosscontract.exceptions import FileReadError

_NA_VALUES = [
    "#N/A N/A",
    "#NA",
    "-1.#IND",
    "-1.#QNAN",
    "-NaN",
    "-nan",
    "1.#IND",
    "1.#QNAN",
    "<NA>",
    "N/A",
    "NULL",
    "NaN",
    "None",
    "n/a",
    "nan",
    "null",
    "undefined",
]


def read_csv_file_bytes(data: bytes) -> pd.DataFrame:
    """Read the content of a CSV file into a DataFrame.

    The content must be UTF-8. Only these tokens become missing values: `#N/A N/A`,
    `#NA`, `-1.#IND`, `-1.#QNAN`, `-NaN`, `-nan`, `1.#IND`, `1.#QNAN`, `<NA>`,
    `N/A`, `NULL`, `NaN`, `None`, `n/a`, `nan`, `null` and `undefined`. Any other
    text, such as the country code `NA`, is kept as a string. An empty cell is kept
    as an empty string, so a single empty cell turns a numeric column into strings.

    Args:
        data (bytes): The content of the CSV file.

    Returns:
        pd.DataFrame: The data of the file.

    Raises:
        FileReadError: If the content is not UTF-8, is not valid CSV or is empty.
    """
    try:
        return pd.read_csv(
            io.BytesIO(data),
            encoding="utf-8",
            encoding_errors="strict",
            keep_default_na=False,
            on_bad_lines="error",
            na_values=_NA_VALUES,
        )
    except UnicodeDecodeError as e:
        raise FileReadError("Invalid file encoding: must be UTF-8") from e
    except pd.errors.ParserError as e:
        raise FileReadError(f"Invalid CSV format: {e}") from e
    except pd.errors.EmptyDataError as e:
        raise FileReadError(f"Could not parse file: {e}") from e


def read_csv_file(filename: str | Path) -> pd.DataFrame:
    """Read a CSV file into a DataFrame.

    Reads the file and passes its content to `read_csv_file_bytes`.

    Args:
        filename (str | Path): The path of the CSV file.

    Returns:
        pd.DataFrame: The data of the file.

    Raises:
        FileNotFoundError: If the file does not exist.
        FileReadError: As raised by `read_csv_file_bytes`.
    """
    return read_csv_file_bytes(Path(filename).read_bytes())
