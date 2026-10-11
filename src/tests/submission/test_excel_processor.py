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


class TestExcelSheet:
    def test_long_sheet_without_description(self):
        sheet = ExcelSheet(name="a")
        assert sheet.description is None
        assert sheet.wide is None

    def test_long_sheet_with_description(self):
        assert ExcelSheet(name="a", description="text").description == "text"

    def test_wide_sheet(self):
        sheet = ExcelSheet(
            name="a", wide=WideLayout(header_field="year", value_field="value")
        )
        assert sheet.wide is not None

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            ExcelSheet(name="")


class TestExtraKeys:
    def test_wide_layout(self):
        with pytest.raises(ValidationError, match="extra"):
            WideLayout.model_validate(
                {"header_field": "a", "value_field": "b", "other": 1}
            )

    def test_sheet(self):
        with pytest.raises(ValidationError, match="extra"):
            ExcelSheet.model_validate({"name": "a", "other": 1})

    def test_processor(self):
        with pytest.raises(ValidationError, match="extra"):
            ExcelProcessor.model_validate({"sheets": [{"name": "a"}], "other": 1})


class TestExcelProcessor:
    def test_empty_sheets_rejected(self):
        with pytest.raises(ValidationError):
            ExcelProcessor(sheets=[])

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

    def test_duplicate_sheet_names_case_insensitive(self):
        with pytest.raises(ValidationError, match="Duplicate sheet names.*costs"):
            ExcelProcessor(sheets=[ExcelSheet(name="Costs"), ExcelSheet(name="costs")])

    def test_unique_sheet_names_accepted(self):
        processor = ExcelProcessor(sheets=[ExcelSheet(name="a"), ExcelSheet(name="b")])
        assert [s.name for s in processor.sheets] == ["a", "b"]
