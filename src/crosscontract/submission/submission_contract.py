"""Contract type for submission bundles.

A submission bundle is a single file carrying several variables at once. The
contract describes that file, records how each variable is extracted from it,
and states how the extracted variables are validated.
"""

from typing import Literal, Self

from pydantic import Field, model_validator

from crosscontract import CrossContract

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

    contract_type: Literal["Submission"] = Field(
        default="Submission", description="Type of the contract."
    )

    project_name: str = Field(
        ...,
        description="The name of the project associated with the submission.",
    )

    extraction: ExtractionInstructions

    @model_validator(mode="after")
    def _check_routing_column(self) -> Self:
        """Check that the routing column exists in the tableschema, that it is
        required and that it is a string column. Also the routing column cannot
        have an enum constraint as this is derived from the ExtractionInstructions.

        Returns:
            Self: The validated SubmissionContract instance.

        Raises:
            ValueError: If the routing column does not exist in the tableschema,
                is not required, is not a string column, or has an enum constraint.
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
        if routing_field.constraints.enum is not None:
            raise ValueError(
                f"Routing column '{routing_column}' cannot have an enum constraint"
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
                    f"Target for contract: {target.contract}: Filter columns "
                    f"{', '.join(sorted(not_valid))} do not exist in the tableschema."
                )
        return self
