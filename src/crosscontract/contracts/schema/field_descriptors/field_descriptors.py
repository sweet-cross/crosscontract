from collections.abc import Iterator
from functools import cached_property
from typing import Annotated

from pydantic import Field, RootModel

from .descriptors import (
    LocationFieldDescriptor,
    TimeFieldDescriptor,
    ValueFieldDescriptor,
)

# --- Union and Root ---
DescriptorUnion = Annotated[
    # Pydantic will check the 'type' field to decide which class to use
    ValueFieldDescriptor | TimeFieldDescriptor | LocationFieldDescriptor,
    Field(discriminator="type"),
]


class FieldDescriptors(RootModel):
    """
    Field descriptors provide semantic information about the fields in a data
    contract.
    """

    root: list[DescriptorUnion] = Field(
        default_factory=list,
        description="A list of semantic field descriptors.",
        min_length=1,
    )

    def __iter__(self) -> Iterator[DescriptorUnion]:  # type: ignore[override]
        return iter(self.root)

    def __getitem__(self, key: int | str) -> DescriptorUnion:
        if isinstance(key, int):
            return self.root[key]
        try:
            return self._name_index[key]
        except KeyError as e:
            raise KeyError(f'Field "{key}" not found in field descriptors.') from e

    def __len__(self) -> int:
        return len(self.root)

    @cached_property
    def _name_index(self) -> dict[str, DescriptorUnion]:
        """
        Creates a dictionary mapping field names to field objects.
        This runs only once when accessed, providing O(1) lookups thereafter.
        """
        return {field.field: field for field in self.root}

    @property
    def names(self) -> list[str]:
        """Returns a list of all field names."""
        return list(self._name_index)

    def get(self, name: str) -> DescriptorUnion | None:
        """Returns the field by name, or None if it doesn't exist.

        Args:
            name (str): The name of the field.

        Returns:
            FieldUnion | None: The field object or None if not found.
        """
        return self._name_index.get(name)

    def validate_all_exist(self, field_names: list[str]) -> None:
        """Validates that all referenced fields exist in the provided list.

        Args:
            field_names (list[str]): List of valid field names.

        Raises:
            ValueError: If any referenced field does not exist.
        """
        given = set(field_names)
        errors = []
        for descriptor in self.root:
            if descriptor.field not in given:
                errors.append(
                    f"Field '{descriptor.field}' referenced in descriptor does "
                    "not exist in schema."
                )
        if errors:
            raise ValueError(" ; ".join(errors))
