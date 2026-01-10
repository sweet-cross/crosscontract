from collections.abc import Iterator

from pydantic import (
    BaseModel,
    Field,
    RootModel,
    field_validator,
    model_validator,
)

from crosscontract.contracts.valid_items import ValidFieldName


class ReferencedField(BaseModel):
    """
    A referenced field contains the name of the contract and the fields
    referenced in that contract.

    Attributes:
        resource (str): The name of the contract that contains the referenced field.
        fields (list[str]): The name of the referenced fields.
    """

    resource: ValidFieldName | None = Field(
        default=None,
        description=(
            "The name of the contract that contains the referenced field. "
            "If not provided, the field is assumed to be in the same contract."
        ),
    )
    # Use ValidFieldName type here so constraints apply to items
    fields: list[ValidFieldName] = Field(
        description=(
            "The name of the referenced fields. Note that in case of a list "
            "of fields, the order of referring and referenced fields is important."
        ),
        min_length=1,  # Ensure at least one field is referenced
    )

    @field_validator("fields", mode="before")
    @classmethod
    def transform_fields_to_list(cls, value: str | list[str]) -> list[str]:
        """Transform the fields input to a list if it is a single string."""
        if isinstance(value, str):
            return [value]
        return value


class ForeignKey(BaseModel):
    """
    A foreign key contains the name of the field within the current contract and
    the reference to the target definition given as a ReferencedField. It is
    assumed that the order of fields in 'fields' matches the order of fields in
    'reference.fields'. Moreover, it is assumed that a single foreign key references
    to fields in a single target resource.

    Attributes:
        fields (list[str]): The name of the fields in the current contract.
        reference (ReferencedField): The target definition.
    """

    fields: list[ValidFieldName] = Field(
        description=(
            "The name of the fields that hold the foreign key references. "
            "Order matches the order in 'reference.fields'."
        ),
        min_length=1,
    )
    reference: ReferencedField = Field(
        description="The referenced field in the foreign key relationship."
    )

    @field_validator("fields", mode="before")
    @classmethod
    def transform_fields_to_list(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [value]
        return value

    @model_validator(mode="after")
    def validate_field_length_match(self) -> "ForeignKey":
        """Ensure source and target have the same number of fields."""
        if len(self.fields) != len(self.reference.fields):
            raise ValueError(
                f"Foreign key length mismatch: Source has {len(self.fields)} fields "
                f"{self.fields}, but target reference has {len(self.reference.fields)} "
                f"fields {self.reference.fields}."
            )
        return self

    def validate_fields(self, field_names: list[str]) -> None:
        """
        Validates that all fields in the primary key exist in the provided
        set of field names.

        Args:
            field_names (list[str]): A list of valid field names.

        Raises:
            ValidationError: If any field in the primary key does not exist in
                the provided field names.
        """
        field_names_set = set(field_names)
        missing_fields = [
            field for field in self.fields if field not in field_names_set
        ]
        if missing_fields:
            raise ValueError(
                f"Foreign key fields {missing_fields} do not exist in the schema."
            )

    def validate_referenced_fields(self, field_names: list[str]) -> None:
        """
        Validates that the fields exist in the referenced resource.

        Args:
            field_names (list[str]): A list of valid referenced field names.

        Raises:
            ValueError: If any referenced field does not exist in
                the provided referenced field names.
        """
        field_names_set = set(field_names)
        missing_fields = [
            field for field in self.reference.fields if field not in field_names_set
        ]
        resource_name = self.reference.resource or "self-reference"
        if missing_fields:
            raise ValueError(
                f"Referenced fields {missing_fields} do not exist in the "
                f"referenced resource. ({resource_name})"
            )


class ForeignKeys(RootModel):
    """
    A foreign key defines a relationship between fields in the current contract
    and fields in the same or another contract.
    """

    root: list[ForeignKey] = Field(
        default_factory=list,
        description="An array of ForeignKeyReference objects.",
    )

    def __iter__(self) -> Iterator[ForeignKey]:  # type: ignore[override]
        return iter(self.root)

    def __len__(self) -> int:
        return len(self.root)
