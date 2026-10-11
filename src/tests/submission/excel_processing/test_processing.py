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
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False)
    return buffer.getvalue()


LONG_SHEET = {"name": "long"}
WIDE_SHEET = {"name": "wide", "wide": {"header_field": "year", "value_field": "value"}}


def test_exported():
    assert submission.read_excel_bundle is read_excel_bundle
    assert submission.read_excel_bundle_bytes is read_excel_bundle_bytes
    assert "read_excel_bundle" in submission.__all__
    assert "read_excel_bundle_bytes" in submission.__all__


def test_long_sheet_unchanged():
    df = read_excel_bundle_bytes(_contract(LONG_SHEET), _workbook(long=LONG))
    pd.testing.assert_frame_equal(df, LONG)


def test_wide_sheet_melted():
    df = read_excel_bundle_bytes(_contract(WIDE_SHEET), _workbook(wide=WIDE))
    assert list(df.columns) == ["region", "variable", "year", "value"]
    assert len(df) == 4
    assert df["year"].tolist() == ["2020", "2020", "2021", "2021"]
    assert df["region"].tolist() == ["CH", "DE", "CH", "DE"]
    assert df["variable"].tolist() == ["gdp"] * 4


def test_wide_blank_cells_kept():
    df = read_excel_bundle_bytes(_contract(WIDE_SHEET), _workbook(wide=WIDE))
    assert df["value"].isna().sum() == 1
    row = df[df["value"].isna()].iloc[0]
    assert (row["region"], row["year"]) == ("DE", "2020")


def test_unlisted_sheet_ignored():
    data = _workbook(long=LONG, other=WIDE)
    df = read_excel_bundle_bytes(_contract(LONG_SHEET), data)
    pd.testing.assert_frame_equal(df, LONG)


def test_sheets_concatenated_in_listed_order():
    data = _workbook(wide=WIDE, long=LONG)
    df = read_excel_bundle_bytes(_contract(LONG_SHEET, WIDE_SHEET), data)
    assert df["variable"].tolist() == ["pop"] * 2 + ["gdp"] * 4
    assert df.index.tolist() == list(range(6))

    df = read_excel_bundle_bytes(_contract(WIDE_SHEET, LONG_SHEET), data)
    assert df["variable"].tolist() == ["gdp"] * 4 + ["pop"] * 2


def test_no_excel_processor():
    with pytest.raises(ValueError, match="has no excel_processor"):
        read_excel_bundle_bytes(_contract(), _workbook(long=LONG))


def test_missing_sheet_skipped():
    data = _workbook(long=LONG)
    df = read_excel_bundle_bytes(_contract(LONG_SHEET, WIDE_SHEET), data)
    pd.testing.assert_frame_equal(df, LONG)


def test_no_listed_sheet_in_workbook():
    with pytest.raises(ValueError, match="None of the listed sheets"):
        read_excel_bundle_bytes(_contract(WIDE_SHEET), _workbook(long=LONG))


def test_header_named_like_header_field_is_melted():
    df = WIDE.assign(year=1)
    out = read_excel_bundle_bytes(_contract(WIDE_SHEET), _workbook(wide=df))
    assert list(out.columns) == ["region", "variable", "year", "value"]
    assert "year" in out["year"].tolist()


def test_misspelled_id_column_becomes_value_var():
    df = WIDE.rename(columns={"region": "region "})
    out = read_excel_bundle_bytes(_contract(WIDE_SHEET), _workbook(wide=df))
    assert "region " not in out.columns
    assert "region " in out["year"].tolist()


def test_read_excel_bundle_from_file(tmp_path: Path):
    fn = tmp_path / "bundle.xlsx"
    fn.write_bytes(_workbook(long=LONG))
    for name in (fn, str(fn)):
        df = read_excel_bundle(_contract(LONG_SHEET), name)
        pd.testing.assert_frame_equal(df, LONG)


def test_read_excel_bundle_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        read_excel_bundle(_contract(LONG_SHEET), tmp_path / "missing.xlsx")


class TestCleanSheet:
    def test_clean_sheet_unchanged(self):
        pd.testing.assert_frame_equal(_clean_sheet(LONG, "s"), LONG)

    def test_empty_rows_dropped(self):
        df = pd.DataFrame({"region": ["CH", None, "DE"], "value": [1.0, None, None]})
        out = _clean_sheet(df, "s")
        pd.testing.assert_frame_equal(out, df.iloc[[0, 2]])

    def test_empty_unnamed_columns_dropped(self):
        df = LONG.assign(**{"Unnamed: 3": None, "Unnamed: 4": float("nan")})
        pd.testing.assert_frame_equal(_clean_sheet(df, "s"), LONG)

    def test_empty_named_column_kept(self):
        df = LONG.assign(comment=None)
        pd.testing.assert_frame_equal(_clean_sheet(df, "s"), df)

    def test_unnamed_column_with_data_raises(self):
        df = LONG.assign(**{"Unnamed: 3": ["x", None], "Unnamed: 4": None})
        with pytest.raises(ValueError, match="Sheet 's'.*Unnamed: 3$"):
            _clean_sheet(df, "s")

    def test_matcher_requires_blank(self):
        df = LONG.assign(**{"Unnamed:3": None})
        pd.testing.assert_frame_equal(_clean_sheet(df, "s"), df)


def test_wide_sheet_cleaned_before_melting():
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
