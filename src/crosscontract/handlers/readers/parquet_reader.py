import io
from pathlib import Path

import pandas as pd
import pyarrow as pa

from crosscontract.exceptions import FileReadError


def read_parquet_file_bytes(data: bytes) -> pd.DataFrame:
    """Read the content of a Parquet file into a DataFrame.

    Args:
        data (bytes): The content of the Parquet file.

    Returns:
        pd.DataFrame: The data of the file.

    Raises:
        FileReadError: If the content is not valid Parquet, is corrupted or is
            empty.
    """
    try:
        return pd.read_parquet(io.BytesIO(data))
    except (pa.ArrowException, OSError) as e:
        raise FileReadError(f"Invalid Parquet format: {e}") from e


def read_parquet_file(filename: str | Path) -> pd.DataFrame:
    """Read a Parquet file into a DataFrame.

    Reads the file and passes its content to `read_parquet_file_bytes`.

    Args:
        filename (str | Path): The path of the Parquet file.

    Returns:
        pd.DataFrame: The data of the file.

    Raises:
        FileNotFoundError: If the file does not exist.
        FileReadError: As raised by `read_parquet_file_bytes`.
    """
    return read_parquet_file_bytes(Path(filename).read_bytes())
