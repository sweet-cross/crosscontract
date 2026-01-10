from collections.abc import Iterator

from pydantic import Field, RootModel, field_validator

from crosscontract.contracts.valid_items import ValidFieldName


class PrimaryKey(RootModel):
    """
    A PrimaryKey defines one or more fields that uniquely identify a record
    within a DataContract.

    Attributes:
        root (list[str]): A list of field names that make up the primary key.
    """

    root: list[ValidFieldName] = Field(
        default_factory=list,
        description="A list of field names that make up the primary key.",
    )

    def __iter__(self) -> Iterator[str]:  # type: ignore[override]
        return iter(self.root)

    def __len__(self) -> int:
        return len(self.root)

    @field_validator("root", mode="before")
    @classmethod
    def transform_primary_key_to_list(cls, v):
        if isinstance(v, str):
            return [v]
        return v

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
        missing_fields = [field for field in self.root if field not in field_names_set]
        if missing_fields:
            raise ValueError(
                f"Primary key fields {missing_fields} do not exist in the schema."
            )
