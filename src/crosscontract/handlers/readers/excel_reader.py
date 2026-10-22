from io import BytesIO
from pathlib import Path

import pandas as pd
from python_calamine import CalamineError

from crosscontract.contracts.readers import ExcelProcessor
from crosscontract.contracts.submission import SubmissionContract
from crosscontract.exceptions import FileReadError

from .constants import NA_VALUES


def _clean_sheet(df: pd.DataFrame, sheet_name: str) -> pd.DataFrame:
    """Drop the empty rows and the empty columns without a header from a sheet.

    pandas names a column with a blank header `Unnamed: N`. Such a column is
    dropped if it holds no data once the empty rows are gone.

    Args:
        df (pd.DataFrame): The sheet as pandas reads it.
        sheet_name (str): The name of the sheet, used in the error message.

    Returns:
        pd.DataFrame: The sheet without empty rows and without columns that have a
            blank header.

    Raises:
        FileReadError: If a column with a blank header holds data.
    """
    df = df.dropna(how="all")
    unnamed = [col for col in df.columns if str(col).startswith("Unnamed: ")]
    with_data = [str(col) for col in unnamed if df[col].notna().any()]
    if with_data:
        raise FileReadError(
            f"Sheet '{sheet_name}': columns without a header hold data: "
            f"{', '.join(with_data)}"
        )
    return df.drop(columns=unnamed)


def read_excel_workbook_bytes(
    processor: ExcelProcessor, field_names: set[str], data: bytes
) -> pd.DataFrame:
    """Read an Excel workbook into one long frame, as the processor describes.

    The sheets listed in `processor` are read by exact name; listed sheets missing
    from the workbook are skipped and other sheets in the workbook are ignored. The
    first row of every sheet holds the column headers. In every sheet, rows that are
    entirely blank are dropped, and so are columns with a blank header that hold no
    data. A long sheet is then taken unchanged. In a wide sheet, the columns named
    in `field_names` are kept as identifiers and every remaining column is melted
    into the `header_field` (the column header) and `value_field` (the cell)
    columns. Blank cells of a wide sheet are kept as rows with a missing value. The
    processed sheets are concatenated in the order they are listed. Only a blank
    cell becomes a missing value; any other text, such as `NA` or `null`, is kept as
    a string. No values are validated.

    Args:
        processor (ExcelProcessor): The sheets of the workbook and their layout.
        field_names (set[str]): The names of the fields a wide sheet may carry as
            identifier columns.
        data (bytes): The content of the Excel workbook.

    Returns:
        pd.DataFrame: The long frame.

    Raises:
        FileReadError: If `data` cannot be read as an Excel workbook.
        FileReadError: If none of the listed sheets is in the workbook.
        FileReadError: If a column with a blank header holds data.
        FileReadError: If a wide sheet has a column named like its `value_field`.
    """
    try:
        excel_file = pd.ExcelFile(BytesIO(data), engine="calamine")

        # Ensure at least one listed sheet is in the workbook
        sheets = [
            sheet for sheet in processor.sheets if sheet.name in excel_file.sheet_names
        ]
        if not sheets:
            raise FileReadError("None of the listed sheets was found in the workbook.")

        # load the data
        workbook = pd.read_excel(
            excel_file,
            sheet_name=[sheet.name for sheet in sheets],
            keep_default_na=False,
            na_values=NA_VALUES,
        )
    except CalamineError as e:
        raise FileReadError(f"Could not read the Excel workbook: {e}") from e

    # extract the frames from each sheet
    frames = []
    for sheet in sheets:
        df = _clean_sheet(workbook[sheet.name], sheet.name)
        if sheet.wide is not None:
            if sheet.wide.value_field in df.columns:
                raise FileReadError(
                    f"Sheet '{sheet.name}': column '{sheet.wide.value_field}' "
                    "is named like the value_field."
                )
            # if wide layout melt the dataframe to long format
            id_vars = [
                col
                for col in df.columns
                if col in field_names and col != sheet.wide.header_field
            ]
            df = df.melt(
                id_vars=id_vars,
                var_name=sheet.wide.header_field,
                value_name=sheet.wide.value_field,
            )
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


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
        FileReadError: If `data` cannot be read as an Excel workbook, none of the
            listed sheets is in it, a column with a blank header holds data, or a
            wide sheet has a column named like its `value_field`.
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
        ValueError: If the contract has no `excel_processor`.
        FileReadError: If the file cannot be read as an Excel workbook, none of the
            listed sheets is in it, a column with a blank header holds data, or a
            wide sheet has a column named like its `value_field`.
    """
    return read_excel_bundle_bytes(contract, Path(filename).read_bytes())
