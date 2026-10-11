import pytest
from pydantic import ValidationError

from crosscontract.submission.excel_processor import (
    ExcelProcessor,
    ExcelSheet,
    WideLayout,
)


class TestWideLayout:
    def test_valid(self):
        layout = WideLayout(header_field="year", value_field="value")
        assert layout.header_field == "year"
        assert layout.value_field == "value"

    def test_equal_fields_rejected(self):
        with pytest.raises(ValidationError, match="must differ"):
            WideLayout(header_field="year", value_field="year")


class TestExcelProcessor:
    def test_valid_yaml_example(self):
        processor = ExcelProcessor.model_validate(
            {
                "sheets": [
                    {
                        "name": "capacities",
                        "description": "Installed capacities per technology.",
                    },
                    {
                        "name": "costs",
                        "wide": {"header_field": "year", "value_field": "value"},
                    },
                ]
            }
        )
        assert processor.sheets[0].wide is None
        assert processor.sheets[1].wide == WideLayout(
            header_field="year", value_field="value"
        )

    def test_duplicate_sheet_names_rejected(self):
        with pytest.raises(ValidationError, match="Duplicate sheet names.*a, b"):
            ExcelProcessor(
                sheets=[
                    ExcelSheet(name="b"),
                    ExcelSheet(name="a"),
                    ExcelSheet(name="a"),
                    ExcelSheet(name="b"),
                    ExcelSheet(name="c"),
                ]
            )

    def test_unique_sheet_names_accepted(self):
        processor = ExcelProcessor(sheets=[ExcelSheet(name="a"), ExcelSheet(name="b")])
        assert [s.name for s in processor.sheets] == ["a", "b"]
