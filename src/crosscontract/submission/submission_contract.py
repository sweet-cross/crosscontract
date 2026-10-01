"""Contract type for submission bundles.

A submission bundle is a single file carrying several variables at once. The
contract describes that file, records how each variable is extracted from it,
and states how the extracted variables are validated.
"""

from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from crosscontract.contracts import ContractResolver, CrossContract

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
            submitted table. Must declare neither `primaryKey` nor
            `foreignKeys`; those belong to the contracts the targets name.
        contract_type (Literal["Submission"]): Fixed discriminator identifying
            this contract type.
        project_name (str): The name of the project the submission belongs to.
        extraction (ExtractionInstructions): Instructions for extracting each
            variable from the submission file.
        replace_key (list[str] | Literal["all"]): The columns whose values
            identify the slice a resubmission replaces, or `all` to replace
            everything previously submitted under this contract. Names columns
            of the target contracts as they land after extraction, not of
            `tableschema`.
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

    replace_key: list[str] | Literal["all"] = Field(
        ...,
        description=(
            "The columns whose values identify the slice a resubmission replaces, "
            "or `all` to replace everything previously submitted under this "
            "contract. Names columns of the target contracts as they land after "
            "extraction, not of `tableschema`. Example: with `['model_id']`, a "
            "submission carrying `model_id=model_a` replaces the rows an earlier "
            "submission delivered under that value."
        ),
    )

    @field_validator("replace_key")
    @classmethod
    def _validate_replace_key(
        cls, v: list[str] | Literal["all"]
    ) -> list[str] | Literal["all"]:
        """Check that a column list is non-empty and names each column once.

        Args:
            v (list[str] | Literal["all"]): The value to check. `all` passes
                through unchecked.

        Returns:
            list[str] | Literal["all"]: The value, unchanged.

        Raises:
            ValueError: If the list is empty or repeats a column name.
        """
        if v == "all":
            return v
        if not v:
            raise ValueError("replace_key must not be empty.")
        duplicates = sorted({column for column in v if v.count(column) > 1})
        if duplicates:
            raise ValueError(f"Duplicate replace_key columns: {', '.join(duplicates)}")
        return v

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

    @model_validator(mode="after")
    def _check_no_primary_key(self) -> Self:
        """Check that the tableschema does not have a primary key.

        Returns:
            Self: The validated SubmissionContract instance.

        Raises:
            ValueError: If the tableschema has a primary key.
        """
        if self.tableschema.primaryKey:
            raise ValueError(
                "Submission contracts must not have primary keys in "
                "their tableschema. They belong to the contracts the targets name"
            )
        return self

    @model_validator(mode="after")
    def _check_no_foreign_keys(self) -> Self:
        """Check that the tableschema does not have foreign keys.

        Returns:
            Self: The validated SubmissionContract instance.

        Raises:
            ValueError: If the tableschema has foreign keys.
        """
        if self.tableschema.foreignKeys:
            raise ValueError(
                "Submission contracts must not have foreign keys in "
                "their tableschema. They belong to the contracts the targets name"
            )
        return self

    def validate_references(
        self,
        resolver: ContractResolver,
        enforce_star_schema: bool = True,
    ) -> None:
        """Validate the contracts the targets name against the replace key.

        Checks that each target's contract resolves and, where `replace_key`
        names columns, that the contract declares every one of them. A column
        the contract does not declare never reaches the target, leaving the
        replace unable to identify the rows it must remove. Whether the column
        is required is not checked, nor is the contract's type, and no stored
        data is read.

        Args:
            resolver (ContractResolver): Lookup for the target contracts by name.
            enforce_star_schema (bool, optional): Has no effect. Defaults to
                `True`.

        Raises:
            ValueError: If one or more target contracts do not resolve, or do
                not declare the replace key. All failures are reported in a
                single exception.
        """
        # `all` leaves nothing to check against the targets.
        key_columns: list[str] = [] if self.replace_key == "all" else self.replace_key
        errors: list[str] = []
        for target in self.extraction.targets:
            target_contract = resolver.resolve(target.contract)
            if target_contract is None:
                errors.append(
                    f"Target '{target.name}': unknown contract '{target.contract}'."
                )
                continue
            missing = [
                column
                for column in key_columns
                if target_contract.tableschema.get(column) is None
            ]
            if missing:
                errors.append(
                    f"Target '{target.name}': contract '{target.contract}' does "
                    f"not declare the replace key column(s) "
                    f"{', '.join(missing)}."
                )
        if errors:
            raise ValueError(
                f"Reference validation failed for '{self.name}':\n  - "
                + "\n  - ".join(errors)
            )
