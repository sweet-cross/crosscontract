from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WideLayout(BaseModel):
    """The wide layout of an Excel sheet.

    In a wide sheet, every `tableschema` field other than `header_field` and
    `value_field` appears as a column. Every remaining column header is a value of
    `header_field`, and the cells below it are values of `value_field`.

    Attributes:
        header_field (str): The `tableschema` field whose values are the column
            headers.
        value_field (str): The `tableschema` field whose values are the cells.
    """

    model_config = ConfigDict(extra="forbid")

    header_field: str = Field(
        ...,
        description=(
            "The tableschema field whose values are the remaining column headers "
            "of the sheet."
        ),
    )
    value_field: str = Field(
        ...,
        description=(
            "The tableschema field whose values are the cells below the remaining "
            "column headers."
        ),
    )

    @model_validator(mode="after")
    def _check_fields_differ(self) -> Self:
        """Check that `header_field` and `value_field` are different fields.

        Returns:
            Self: The validated instance of WideLayout.

        Raises:
            ValueError: If both fields are equal.
        """
        if self.header_field == self.value_field:
            raise ValueError(
                "header_field and value_field must differ, "
                f"both are '{self.header_field}'."
            )
        return self


class ExcelSheet(BaseModel):
    """A sheet of an Excel bundle.

    Attributes:
        name (str): The fixed name of the sheet in the workbook.
        description (str | None): What the sheet contains.
        wide (WideLayout | None): The wide layout of the sheet. If `None`, the sheet
            is long and used as is.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        ...,
        min_length=1,
        description=(
            "The fixed name of the sheet in the workbook. A sheet is identified by "
            "this name, which must match the workbook's sheet name exactly."
        ),
    )
    description: str | None = Field(
        default=None,
        description="A description of what the sheet contains.",
    )
    wide: WideLayout | None = Field(
        default=None,
        description=(
            "The wide layout of the sheet. A sheet without `wide` is long and is "
            "used as is. In a wide sheet, every tableschema field other than "
            "`header_field` and `value_field` appears as a column, every remaining "
            "column header is a value of `header_field`, and the cells are values "
            "of `value_field`."
        ),
    )


class ExcelProcessor(BaseModel):
    """The sheets of an Excel bundle and how they are laid out.

    Attributes:
        sheets (list[ExcelSheet]): The sheets of the workbook.
    """

    model_config = ConfigDict(extra="forbid")

    sheets: list[ExcelSheet] = Field(
        ...,
        min_length=1,
        description=(
            "The sheets of the workbook, identified by their names, which must be "
            "unique ignoring case."
        ),
    )

    @model_validator(mode="after")
    def _check_name_unique(self) -> Self:
        """Check that each sheet name is unique in the sheets list, ignoring case.

        Returns:
            Self: The validated instance of ExcelProcessor.

        Raises:
            ValueError: If a name is repeated in the sheets list.
        """
        names = [sheet.name.lower() for sheet in self.sheets]
        duplicates = {name for name in names if names.count(name) > 1}
        if duplicates:
            raise ValueError(
                "Duplicate sheet names found in sheets:"
                f" {', '.join(sorted(duplicates))}"
            )
        return self
