from io import BytesIO

import pandas as pd

from .specs import ExcelProcessor


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
        ValueError: If a column with a blank header holds data.
    """
    df = df.dropna(how="all")
    unnamed = [col for col in df.columns if str(col).startswith("Unnamed: ")]
    with_data = [str(col) for col in unnamed if df[col].notna().any()]
    if with_data:
        raise ValueError(
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
    processed sheets are concatenated in the order they are listed. Header and cell
    values are left as pandas reads them, and no values are validated.

    Args:
        processor (ExcelProcessor): The sheets of the workbook and their layout.
        field_names (set[str]): The names of the fields a wide sheet may carry as
            identifier columns.
        data (bytes): The content of the Excel workbook.

    Returns:
        pd.DataFrame: The long frame.

    Raises:
        ValueError: If none of the listed sheets is in the workbook.
        ValueError: If a column with a blank header holds data.
        ValueError: If a wide sheet has a column named like its `value_field`.
        python_calamine.CalamineError: If `data` cannot be read as an Excel
            workbook.
    """
    # Ensure at least one listed sheet is in the workbook
    excel_file = pd.ExcelFile(BytesIO(data), engine="calamine")
    sheets = [
        sheet for sheet in processor.sheets if sheet.name in excel_file.sheet_names
    ]
    if not sheets:
        raise ValueError("None of the listed sheets was found in the workbook.")

    # load the data
    workbook = pd.read_excel(excel_file, sheet_name=[sheet.name for sheet in sheets])

    # extract the frames from each sheet
    frames = []
    for sheet in sheets:
        df = _clean_sheet(workbook[sheet.name], sheet.name)
        if sheet.wide is not None:
            if sheet.wide.value_field in df.columns:
                raise ValueError(
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
