import pytest
from pydantic import ValidationError

from crosscontract.submission.excel_processing import (
    ExcelProcessor,
    ExcelSheet,
    WideLayout,
)


class TestWideLayout:
    def test_valid(self):
        """Test that a wide layout keeps its `header_field` and `value_field`."""
        layout = WideLayout(header_field="year", value_field="value")
        assert layout.header_field == "year"
        assert layout.value_field == "value"

    def test_equal_fields_rejected(self):
        """Test that equal `header_field` and `value_field` are rejected."""
        with pytest.raises(ValidationError, match="must differ"):
            WideLayout(header_field="year", value_field="year")


class TestExcelSheet:
    def test_long_sheet_without_description(self):
        """Test that a sheet without `wide` is long and has no description."""
        sheet = ExcelSheet(name="a")
        assert sheet.description is None
        assert sheet.wide is None

    def test_long_sheet_with_description(self):
        """Test that a sheet keeps its `description`."""
        assert ExcelSheet(name="a", description="text").description == "text"

    def test_wide_sheet(self):
        """Test that a sheet keeps its `wide` layout."""
        sheet = ExcelSheet(
            name="a", wide=WideLayout(header_field="year", value_field="value")
        )
        assert sheet.wide == WideLayout(header_field="year", value_field="value")

    def test_empty_name_rejected(self):
        """Test that an empty sheet name is rejected."""
        with pytest.raises(ValidationError):
            ExcelSheet(name="")


class TestExtraKeys:
    def test_wide_layout(self):
        """Test that a wide layout rejects unknown keys."""
        with pytest.raises(ValidationError, match="extra"):
            WideLayout.model_validate(
                {"header_field": "a", "value_field": "b", "other": 1}
            )

    def test_sheet(self):
        """Test that a sheet rejects unknown keys."""
        with pytest.raises(ValidationError, match="extra"):
            ExcelSheet.model_validate({"name": "a", "other": 1})

    def test_processor(self):
        """Test that a processor rejects unknown keys."""
        with pytest.raises(ValidationError, match="extra"):
            ExcelProcessor.model_validate({"sheets": [{"name": "a"}], "other": 1})


class TestExcelProcessor:
    def test_empty_sheets_rejected(self):
        """Test that a processor without sheets is rejected."""
        with pytest.raises(ValidationError):
            ExcelProcessor(sheets=[])

    def test_valid_yaml_example(self):
        """Test that the documented YAML example with one long and one wide sheet
        validates."""
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
        """Test that repeated sheet names are rejected, naming each duplicate once."""
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
        """Test that sheet names differing only in case count as duplicates."""
        with pytest.raises(ValidationError, match="Duplicate sheet names.*costs"):
            ExcelProcessor(sheets=[ExcelSheet(name="Costs"), ExcelSheet(name="costs")])

    def test_unique_sheet_names_accepted(self):
        """Test that unique sheet names are accepted in their given order."""
        processor = ExcelProcessor(sheets=[ExcelSheet(name="a"), ExcelSheet(name="b")])
        assert [s.name for s in processor.sheets] == ["a", "b"]
