from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest

import crosscontract.crossclient.services.submission as submission
from crosscontract.contracts.submission import SubmissionContract
from crosscontract.crossclient.services.submission import (
    read_excel_bundle,
    read_excel_bundle_bytes,
)

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
    """Test that both readers are exported from `crosscontract.crossclient.services.submission`."""
    assert submission.read_excel_bundle is read_excel_bundle
    assert submission.read_excel_bundle_bytes is read_excel_bundle_bytes
    assert "read_excel_bundle" in submission.__all__
    assert "read_excel_bundle_bytes" in submission.__all__


def test_long_sheet_unchanged():
    """Test that a long sheet is returned unchanged."""
    df = read_excel_bundle_bytes(_contract(LONG_SHEET), _workbook(long=LONG))
    pd.testing.assert_frame_equal(df, LONG)


def test_wide_sheet_melted():
    """Test that a wide sheet is melted with the `tableschema` fields kept as
    identifier columns."""
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


def test_no_excel_processor():
    """Test that a contract without `excel_processor` raises."""
    with pytest.raises(ValueError, match="has no excel_processor"):
        read_excel_bundle_bytes(_contract(), _workbook(long=LONG))


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
