from io import BytesIO
from zipfile import ZipFile

import openpyxl
import pandas as pd
import pytest

from crosscontract.contracts.readers import ExcelProcessor
from crosscontract.exceptions import FileReadError
from crosscontract.handlers.readers import read_excel_workbook_bytes
from crosscontract.handlers.readers.excel_reader import _clean_sheet

LONG = pd.DataFrame(
    {"region": ["CH", "DE"], "variable": ["pop", "pop"], "value": [1.5, 2.5]}
)
WIDE = pd.DataFrame(
    {
        "region": ["CH", "DE"],
        "variable": ["gdp", "gdp"],
        "2020": [1.0, None],
        "2021": [3.0, 4.0],
    }
)


FIELDS = {"region", "variable", "year", "value"}


def _read(data: bytes, *sheets: dict) -> pd.DataFrame:
    """Read a workbook with a processor listing the given sheets.

    Args:
        data (bytes): The content of the workbook.
        *sheets (dict): The processor's sheet entries.

    Returns:
        pd.DataFrame: The long frame.
    """
    processor = ExcelProcessor.model_validate({"sheets": list(sheets)})
    return read_excel_workbook_bytes(processor, FIELDS, data)


def _workbook(**sheets: pd.DataFrame) -> bytes:
    """Write frames into an in-memory Excel workbook.

    Args:
        **sheets (pd.DataFrame): One frame per sheet, keyed by sheet name.

    Returns:
        bytes: The content of the workbook.
    """
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False)
    return buffer.getvalue()


LONG_SHEET = {"name": "long"}
WIDE_SHEET = {"name": "wide", "wide": {"header_field": "year", "value_field": "value"}}


def test_long_sheet_unchanged():
    """Test that a long sheet is returned unchanged."""
    df = _read(_workbook(long=LONG), LONG_SHEET)
    pd.testing.assert_frame_equal(df, LONG)


def test_wide_sheet_melted():
    """Test that each cell of a wide sheet lands in the row of its id values and
    header, with blank cells kept as missing values."""
    df = _read(_workbook(wide=WIDE), WIDE_SHEET)
    expected = pd.DataFrame(
        {
            "region": ["CH", "DE", "CH", "DE"],
            "variable": ["gdp"] * 4,
            "year": ["2020", "2020", "2021", "2021"],
            "value": [1.0, None, 3.0, 4.0],
        }
    )
    pd.testing.assert_frame_equal(df, expected)


def test_wide_int_headers_left_as_read():
    """Test that number headers of a wide sheet come back as `int`, unconverted."""
    wide = pd.DataFrame({"region": ["CH"], "variable": ["gdp"], 2020: [1], 2021: [2]})
    df = _read(_workbook(wide=wide), WIDE_SHEET)
    assert df["year"].tolist() == [2020, 2021]
    assert all(type(year) is int for year in df["year"])


def test_unlisted_sheet_ignored():
    """Test that a workbook sheet the contract does not list is ignored."""
    data = _workbook(long=LONG, other=WIDE)
    df = _read(data, LONG_SHEET)
    pd.testing.assert_frame_equal(df, LONG)


def test_sheets_concatenated_in_listed_order():
    """Test that sheets are concatenated in the order the contract lists them,
    with a fresh index."""
    data = _workbook(wide=WIDE, long=LONG)
    df = _read(data, LONG_SHEET, WIDE_SHEET)
    assert df["variable"].tolist() == ["pop"] * 2 + ["gdp"] * 4
    assert df.index.tolist() == list(range(6))

    df = _read(data, WIDE_SHEET, LONG_SHEET)
    assert df["variable"].tolist() == ["gdp"] * 4 + ["pop"] * 2


def test_missing_sheet_skipped():
    """Test that a listed sheet missing from the workbook is skipped."""
    data = _workbook(long=LONG)
    df = _read(data, LONG_SHEET, WIDE_SHEET)
    pd.testing.assert_frame_equal(df, LONG)


def test_sheet_name_matched_exactly():
    """Test that a sheet whose name differs only in case is not matched and is
    skipped."""
    data = _workbook(long=LONG, Wide=WIDE)
    df = _read(data, LONG_SHEET, WIDE_SHEET)
    pd.testing.assert_frame_equal(df, LONG)


def test_no_listed_sheet_in_workbook():
    """Test that a workbook holding none of the listed sheets raises."""
    with pytest.raises(FileReadError, match="None of the listed sheets"):
        _read(_workbook(long=LONG), WIDE_SHEET)


def test_corrupt_workbook_raises():
    """Test that bytes that are not a workbook raise."""
    with pytest.raises(FileReadError, match="Could not read the Excel workbook"):
        _read(b"not a workbook", LONG_SHEET)


def test_broken_sheet_raises():
    """Test that a workbook whose sheet data cannot be parsed raises."""
    source = ZipFile(BytesIO(_workbook(long=LONG)))
    buffer = BytesIO()
    with ZipFile(buffer, "w") as broken:
        for item in source.infolist():
            content = source.read(item.filename)
            if item.filename.startswith("xl/worksheets/sheet"):
                content = content[: len(content) // 2]
            broken.writestr(item, content)
    with pytest.raises(FileReadError, match="Could not read the Excel workbook"):
        _read(buffer.getvalue(), LONG_SHEET)


def test_header_named_like_header_field_is_melted():
    """Test that a wide header equal to `header_field` is melted as a value of
    `header_field`, not kept as an id column."""
    df = WIDE.assign(year=[5.0, 6.0])
    out = _read(_workbook(wide=df), WIDE_SHEET)
    assert list(out.columns) == ["region", "variable", "year", "value"]
    assert len(out) == 6
    melted = out[out["year"] == "year"]
    assert melted["region"].tolist() == ["CH", "DE"]
    assert melted["value"].tolist() == [5.0, 6.0]


def test_header_named_like_value_field_raises():
    """Test that a wide header equal to `value_field` raises, naming the
    sheet."""
    df = WIDE.assign(value=1)
    with pytest.raises(FileReadError, match="Sheet 'wide'.*'value'"):
        _read(_workbook(wide=df), WIDE_SHEET)


def test_duplicate_wide_headers_renamed_by_pandas():
    """Test that repeated headers of a wide sheet come back as pandas renames
    them."""
    wide = pd.DataFrame(
        [["CH", "gdp", 1.0, 2.0]], columns=["region", "variable", "2020", "2020"]
    )
    df = _read(_workbook(wide=wide), WIDE_SHEET)
    assert df["year"].tolist() == ["2020", "2020.1"]


def test_misspelled_id_column_becomes_value_var():
    """Test that a misspelled id column is melted as a header instead of kept as
    an id column."""
    df = WIDE.rename(columns={"region": "region "})
    out = _read(_workbook(wide=df), WIDE_SHEET)
    assert "region " not in out.columns
    assert "region " in out["year"].tolist()


class TestCleanSheet:
    def test_clean_sheet_unchanged(self):
        """Test that a sheet without empty rows or unnamed columns is unchanged."""
        pd.testing.assert_frame_equal(_clean_sheet(LONG, "s"), LONG)

    def test_empty_rows_dropped(self):
        """Test that rows that are entirely blank are dropped."""
        df = pd.DataFrame({"region": ["CH", None, "DE"], "value": [1.0, None, None]})
        out = _clean_sheet(df, "s")
        pd.testing.assert_frame_equal(out, df.iloc[[0, 2]])

    def test_empty_unnamed_columns_dropped(self):
        """Test that unnamed columns without data are dropped."""
        df = LONG.assign(**{"Unnamed: 3": None, "Unnamed: 4": float("nan")})
        pd.testing.assert_frame_equal(_clean_sheet(df, "s"), LONG)

    def test_empty_named_column_kept(self):
        """Test that an empty column with a header is kept."""
        df = LONG.assign(comment=None)
        pd.testing.assert_frame_equal(_clean_sheet(df, "s"), df)

    def test_unnamed_column_with_data_raises(self):
        """Test that an unnamed column holding data raises, naming the sheet and only
        that column."""
        df = LONG.assign(**{"Unnamed: 3": ["x", None], "Unnamed: 4": None})
        with pytest.raises(FileReadError, match="Sheet 's'.*Unnamed: 3$"):
            _clean_sheet(df, "s")

    def test_matcher_requires_blank(self):
        """Test that a column named `Unnamed:` without the blank is not matched."""
        df = LONG.assign(**{"Unnamed:3": None})
        pd.testing.assert_frame_equal(_clean_sheet(df, "s"), df)


def test_wide_sheet_cleaned_before_melting():
    """Test that empty rows and an empty unnamed column of a wide workbook sheet
    are dropped before melting."""
    workbook = openpyxl.Workbook()
    ws = workbook.active
    ws.title = "wide"
    ws.append(["region", "variable", None, "2020"])
    ws.append(["CH", "gdp", None, 1.0])
    ws.append([None, None, None, None])
    ws.append(["DE", "gdp", None, 2.0])
    buffer = BytesIO()
    workbook.save(buffer)

    df = _read(buffer.getvalue(), WIDE_SHEET)
    assert list(df.columns) == ["region", "variable", "year", "value"]
    assert df["region"].tolist() == ["CH", "DE"]
    assert df["year"].tolist() == ["2020", "2020"]


def test_na_tokens_read_as_strings_and_blank_as_missing():
    """Test that NA-like text stays a string while a blank cell is missing."""
    df = pd.DataFrame(
        {
            "region": ["NA", "NULL", "n/a", "None", "CH"],
            "variable": ["pop"] * 5,
            "value": [1.0, 2.0, 3.0, 4.0, None],
        }
    )
    out = _read(_workbook(long=df), LONG_SHEET)
    assert out["region"].tolist() == ["NA", "NULL", "n/a", "None", "CH"]
    assert pd.isna(out["value"].iloc[4])
    assert out["value"].iloc[:4].tolist() == [1.0, 2.0, 3.0, 4.0]


def test_blank_rows_and_blank_header_column_dropped():
    """Test that blank rows and an empty blank-header column are dropped without
    error."""
    workbook = openpyxl.Workbook()
    ws = workbook.active
    ws.title = "long"
    ws.append(["region", "variable", None, "value"])
    ws.append(["CH", "pop", None, 1.0])
    ws.append([None, None, None, None])
    ws.append(["DE", "pop", None, 2.0])
    buffer = BytesIO()
    workbook.save(buffer)

    out = _read(buffer.getvalue(), LONG_SHEET)
    assert list(out.columns) == ["region", "variable", "value"]
    assert out["region"].tolist() == ["CH", "DE"]
