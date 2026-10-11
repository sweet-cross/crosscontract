from io import BytesIO
from pathlib import Path

import openpyxl
import pandas as pd
import pytest

import crosscontract.submission as submission
from crosscontract.submission import (
    SubmissionContract,
    read_excel_bundle,
    read_excel_bundle_bytes,
)
from crosscontract.submission.excel_processing.processing import _clean_sheet

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


def _contract(*sheets: dict) -> SubmissionContract:
    """Build a submission contract with the given sheets.

    Args:
        *sheets (dict): The `excel_processor` sheet entries. If none are given, the
            contract has no `excel_processor`.

    Returns:
        SubmissionContract: The contract.
    """
    data = {
        "name": "submission1",
        "title": "Test Submission",
        "description": "A test submission contract.",
        "project_name": "project1",
        "replace_key": "all",
        "tableschema": {
            "fields": [
                {"name": "region", "type": "string"},
                {
                    "name": "variable",
                    "type": "string",
                    "constraints": {"required": True},
                },
                {"name": "year", "type": "string"},
                {"name": "value", "type": "number"},
            ]
        },
        "extraction": {
            "routing_column": "variable",
            "targets": [
                {
                    "name": "target1",
                    "filters": {"variable": "pop"},
                    "contract": "contract1",
                }
            ],
        },
    }
    if sheets:
        data["excel_processor"] = {"sheets": list(sheets)}
    return SubmissionContract.model_validate(data)


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


def test_exported():
    """Test that both readers are exported from `crosscontract.submission`."""
    assert submission.read_excel_bundle is read_excel_bundle
    assert submission.read_excel_bundle_bytes is read_excel_bundle_bytes
    assert "read_excel_bundle" in submission.__all__
    assert "read_excel_bundle_bytes" in submission.__all__


def test_long_sheet_unchanged():
    """Test that a long sheet is returned unchanged."""
    df = read_excel_bundle_bytes(_contract(LONG_SHEET), _workbook(long=LONG))
    pd.testing.assert_frame_equal(df, LONG)


def test_wide_sheet_melted():
    """Test that each cell of a wide sheet lands in the row of its id values and
    header, with blank cells kept as missing values."""
    df = read_excel_bundle_bytes(_contract(WIDE_SHEET), _workbook(wide=WIDE))
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
    df = read_excel_bundle_bytes(_contract(WIDE_SHEET), _workbook(wide=wide))
    assert df["year"].tolist() == [2020, 2021]
    assert all(type(year) is int for year in df["year"])


def test_unlisted_sheet_ignored():
    """Test that a workbook sheet the contract does not list is ignored."""
    data = _workbook(long=LONG, other=WIDE)
    df = read_excel_bundle_bytes(_contract(LONG_SHEET), data)
    pd.testing.assert_frame_equal(df, LONG)


def test_sheets_concatenated_in_listed_order():
    """Test that sheets are concatenated in the order the contract lists them,
    with a fresh index."""
    data = _workbook(wide=WIDE, long=LONG)
    df = read_excel_bundle_bytes(_contract(LONG_SHEET, WIDE_SHEET), data)
    assert df["variable"].tolist() == ["pop"] * 2 + ["gdp"] * 4
    assert df.index.tolist() == list(range(6))

    df = read_excel_bundle_bytes(_contract(WIDE_SHEET, LONG_SHEET), data)
    assert df["variable"].tolist() == ["gdp"] * 4 + ["pop"] * 2


def test_no_excel_processor():
    """Test that a contract without `excel_processor` raises."""
    with pytest.raises(ValueError, match="has no excel_processor"):
        read_excel_bundle_bytes(_contract(), _workbook(long=LONG))


def test_missing_sheet_skipped():
    """Test that a listed sheet missing from the workbook is skipped."""
    data = _workbook(long=LONG)
    df = read_excel_bundle_bytes(_contract(LONG_SHEET, WIDE_SHEET), data)
    pd.testing.assert_frame_equal(df, LONG)


def test_sheet_name_matched_exactly():
    """Test that a sheet whose name differs only in case is not matched and is
    skipped."""
    data = _workbook(long=LONG, Wide=WIDE)
    df = read_excel_bundle_bytes(_contract(LONG_SHEET, WIDE_SHEET), data)
    pd.testing.assert_frame_equal(df, LONG)


def test_no_listed_sheet_in_workbook():
    """Test that a workbook holding none of the listed sheets raises."""
    with pytest.raises(ValueError, match="None of the listed sheets"):
        read_excel_bundle_bytes(_contract(WIDE_SHEET), _workbook(long=LONG))


def test_header_named_like_header_field_is_melted():
    """Test that a wide header equal to `header_field` is melted as a value of
    `header_field`, not kept as an id column."""
    df = WIDE.assign(year=[5.0, 6.0])
    out = read_excel_bundle_bytes(_contract(WIDE_SHEET), _workbook(wide=df))
    assert list(out.columns) == ["region", "variable", "year", "value"]
    assert len(out) == 6
    melted = out[out["year"] == "year"]
    assert melted["region"].tolist() == ["CH", "DE"]
    assert melted["value"].tolist() == [5.0, 6.0]


def test_header_named_like_value_field_raises():
    """Test that a wide header equal to `value_field` raises pandas' melt error."""
    df = WIDE.assign(value=1)
    with pytest.raises(ValueError, match="value_name"):
        read_excel_bundle_bytes(_contract(WIDE_SHEET), _workbook(wide=df))


def test_misspelled_id_column_becomes_value_var():
    """Test that a misspelled id column is melted as a header instead of kept as
    an id column."""
    df = WIDE.rename(columns={"region": "region "})
    out = read_excel_bundle_bytes(_contract(WIDE_SHEET), _workbook(wide=df))
    assert "region " not in out.columns
    assert "region " in out["year"].tolist()


def test_read_excel_bundle_from_file(tmp_path: Path):
    """Test that the path reader accepts `Path` and `str` and returns the same
    frame as the bytes reader."""
    fn = tmp_path / "bundle.xlsx"
    fn.write_bytes(_workbook(long=LONG))
    for name in (fn, str(fn)):
        df = read_excel_bundle(_contract(LONG_SHEET), name)
        pd.testing.assert_frame_equal(df, LONG)


def test_read_excel_bundle_missing_file(tmp_path: Path):
    """Test that the path reader raises for a missing file."""
    with pytest.raises(FileNotFoundError):
        read_excel_bundle(_contract(LONG_SHEET), tmp_path / "missing.xlsx")


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
        with pytest.raises(ValueError, match="Sheet 's'.*Unnamed: 3$"):
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

    df = read_excel_bundle_bytes(_contract(WIDE_SHEET), buffer.getvalue())
    assert list(df.columns) == ["region", "variable", "year", "value"]
    assert df["region"].tolist() == ["CH", "DE"]
    assert df["year"].tolist() == ["2020", "2020"]
