from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from ..submission_contract import SubmissionContract


def read_excel_bundle_bytes(
    contract: "SubmissionContract", data: bytes
) -> pd.DataFrame:
    """Read an Excel workbook into the long bundle the contract describes.

    The sheets listed in `contract.excel_processor` are read by exact name; listed
    sheets missing from the workbook are skipped and other sheets in the workbook
    are ignored. A long sheet is taken unchanged. In a wide
    sheet, the columns that are `tableschema` fields are kept as identifiers and
    every remaining column is melted into the `header_field` (the column header)
    and `value_field` (the cell) columns. Blank cells of a wide sheet are kept as
    rows with a missing value. The processed sheets are concatenated in the order
    they are listed. Header and cell values are left as pandas reads them, and no
    values are validated.

    Args:
        contract (SubmissionContract): The contract describing the bundle.
        data (bytes): The content of the Excel workbook.

    Returns:
        pd.DataFrame: The long bundle.

    Raises:
        ValueError: If the contract has no `excel_processor`.
        ValueError: If none of the listed sheets is in the workbook.
        ValueError: If the processed sheets contain no data.
        ValueError: If a wide sheet has a column named like its `value_field`.
    """
    if contract.excel_processor is None:
        raise ValueError(f"Contract '{contract.name}' has no excel_processor.")

    # Ensure at least one sheet is listed in the contract
    excel_file = pd.ExcelFile(BytesIO(data), engine="calamine")
    sheets = [
        sheet
        for sheet in contract.excel_processor.sheets
        if sheet.name in excel_file.sheet_names
    ]
    if not sheets:
        raise ValueError("None of the listed sheets was found in the workbook.")

    # load the data
    workbook = pd.read_excel(excel_file, sheet_name=[sheet.name for sheet in sheets])
    field_names = {field.name for field in contract.tableschema.fields}

    # extract the frames from each sheet
    frames = []
    for sheet in sheets:
        df = workbook[sheet.name]
        if sheet.wide is not None:
            # if wide layout melt the dataframe to long format
            id_vars = [
                col
                for col in df.columns
                if col in field_names
                and col not in (sheet.wide.header_field, sheet.wide.value_field)
            ]
            value_vars = [col for col in df.columns if col not in id_vars]
            df = df.melt(
                id_vars=id_vars,
                value_vars=value_vars,
                var_name=sheet.wide.header_field,
                value_name=sheet.wide.value_field,
            )
        frames.append(df)
    bundle = pd.concat(frames, ignore_index=True)
    if bundle.empty:
        raise ValueError("The listed sheets of the workbook contain no data.")
    return bundle


def read_excel_bundle(
    contract: "SubmissionContract", filename: str | Path
) -> pd.DataFrame:
    """Read an Excel file into the long bundle the contract describes.

    Reads the file and passes its content to `read_excel_bundle_bytes`, which
    describes the expected workbook layout.

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
