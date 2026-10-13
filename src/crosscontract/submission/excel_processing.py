from pathlib import Path

import pandas as pd

from crosscontract.contracts.submission import SubmissionContract
from crosscontract.transformations.excel import read_excel_workbook_bytes


def read_excel_bundle_bytes(contract: SubmissionContract, data: bytes) -> pd.DataFrame:
    """Read an Excel workbook into the long bundle the contract describes.

    Reads the sheets listed in `contract.excel_processor` with
    `read_excel_workbook_bytes`, which describes the expected workbook layout. The
    `tableschema` fields are the columns a wide sheet keeps as identifiers.

    Args:
        contract (SubmissionContract): The contract describing the bundle.
        data (bytes): The content of the Excel workbook.

    Returns:
        pd.DataFrame: The long bundle.

    Raises:
        ValueError: If the contract has no `excel_processor`.
        ValueError: As raised by `read_excel_workbook_bytes`.
        python_calamine.CalamineError: If `data` cannot be read as an Excel
            workbook.
    """
    if contract.excel_processor is None:
        raise ValueError(f"Contract '{contract.name}' has no excel_processor.")
    field_names = {field.name for field in contract.tableschema.fields}
    return read_excel_workbook_bytes(contract.excel_processor, field_names, data)


def read_excel_bundle(
    contract: SubmissionContract, filename: str | Path
) -> pd.DataFrame:
    """Read an Excel file into the long bundle the contract describes.

    Reads the file and passes its content to `read_excel_bundle_bytes`.

    Args:
        contract (SubmissionContract): The contract describing the bundle.
        filename (str | Path): The path of the Excel file.

    Returns:
        pd.DataFrame: The long bundle.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: As raised by `read_excel_bundle_bytes`.
    """
    return read_excel_bundle_bytes(contract, Path(filename).read_bytes())
