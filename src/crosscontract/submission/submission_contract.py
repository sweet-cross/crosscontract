"""Contract type for submission bundles.

A submission bundle is a single file carrying several variables at once. The
contract describes that file, records how each variable is extracted from it,
and states how the extracted variables are validated.
"""

from typing import Literal, Self

import pandas as pd
from pydantic import Field, model_validator

from crosscontract.contracts import CrossContract

from .extraction import ExtractionInstructions


class SubmissionContract(CrossContract):
    """A contract describing a submitted file that bundles several variables.

    Unlike a variable contract, which describes one table, a submission contract
    describes the delivered file as a whole: the table it lands as, the project
    it belongs to, and the instructions for extracting each
    variable out of it.

    Attributes:
        name (str): A unique identifier for the contract. Inherited from
            `BaseContract`.
        title (str): A human-readable title for the submission.
        description (str): A human-readable description of the submission.
        tags (list[str]): Tags used for categorization and filtering.
        tableschema (TableSchema): The Frictionless Table Schema describing the
            submitted table.
        contract_type (Literal["Submission"]): Fixed discriminator identifying
            this contract type.
        project_name (str): The name of the project the submission belongs to.
        extraction (ExtractionInstructions): Instructions for extracting each
            variable from the submission file.
    """

    contract_type: Literal["Submission"] = Field(  # type: ignore[assignment]
        default="Submission", description="Type of the contract."
    )

    project_name: str = Field(
        ...,
        description="The name of the project associated with the submission.",
    )

    extraction: ExtractionInstructions = Field(
        ...,
        description=(
            "Instructions for splitting the submission bundle into the datasets "
            "extracted from it."
        ),
    )

    @model_validator(mode="after")
    def _check_routing_column(self) -> Self:
        """Check that the routing column exists in the tableschema, that it is
        required and that it is a string column.

        Returns:
            Self: The validated SubmissionContract instance.

        Raises:
            ValueError: If the routing column does not exist in the tableschema,
                is not required, or is not a string column.
        """
        routing_column = self.extraction.routing_column
        routing_field = self.tableschema.get(routing_column)
        if routing_field is None:
            raise ValueError(
                f"Routing column '{routing_column}' does not exist in the tableschema."
            )
        if not routing_field.constraints.required:
            raise ValueError(f"Routing column '{routing_column}' must be required")
        if routing_field.type != "string":
            raise ValueError(
                f"Routing column '{routing_column}' must be a string column"
            )
        return self

    @model_validator(mode="after")
    def _check_filters(self) -> Self:
        """Check that every filter key names a field in the tableschema.

        Returns:
            Self: The validated SubmissionContract instance.

        Raises:
            ValueError: If a target filters on a column absent from the
                tableschema.
        """
        field_set = set(self.tableschema.field_names)
        for target in self.extraction.targets:
            used_filter_columns = set(target.filters.keys())
            not_valid = used_filter_columns - field_set
            if not_valid:
                raise ValueError(
                    f"Target: {target.name}: Filter columns "
                    f"{', '.join(sorted(not_valid))} do not exist in the tableschema."
                )
        return self

    def unclaimed_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return the rows of a submission bundle that no target claims.

        A row is claimed by a target when it satisfies every entry of that
        target's `filters`. Filter values are matched against the string form
        of the column, so a filter on a typed column compares against
        `str(value)` rather than against the typed value.

        Rows that no target claims are the rows extraction would silently drop.
        This method reports them and nothing more — whether an unclaimed row is
        an error or a warning is the caller's decision.

        Args:
            df (pd.DataFrame): The submission bundle, conforming to
                `tableschema`. Every column named by a target's `filters` must
                be present.

        Returns:
            pd.DataFrame: The unclaimed rows, keeping their index labels. Empty
                when every row is claimed.
        """
        # filters use string comparison
        filter_columns = {c for t in self.extraction.targets for c in t.filters}
        as_str = df[list(filter_columns)].astype(str)

        claimed = pd.Series(False, index=df.index)
        for target in self.extraction.targets:
            matches = pd.Series(True, index=df.index)
            for column, value in target.filters.items():
                matches &= as_str[column] == value
            claimed |= matches
        return df[~claimed]
