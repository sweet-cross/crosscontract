from typing import Self

from pydantic import model_validator

from ..schema import TableSchema


class BaseDimensionSchema(TableSchema):
    """
    (Abstract) Base class for dimension schemas. This class is not meant to be
    instantiated directly but serves as a base for specific dimension schemas.

    Used to enforce the star-schema structure of dimensions, which requires an
    explicitly defined primary key. Foreign keys are optional, but if provided,
    they must all be self-referencing. Multiple self-referencing foreign keys
    are allowed, and no external foreign keys are permitted.

    The primary key can be a single field or a composite key, but it must be
    explicitly defined by the user.
    """

    @model_validator(mode="after")
    def _reject_abstract_instantiation(self) -> Self:
        """Prevents direct instantiation of the abstract base class."""
        if type(self) is BaseDimensionSchema:
            raise TypeError(
                "BaseDimensionSchema is abstract; use a concrete subclass "
                "like FlexibleDimensionSchema."
            )
        return self

    @model_validator(mode="after")
    def _validate_primary_key_defined(self) -> Self:
        """Ensures that a primary key is explicitly defined."""
        if not self.primaryKey or not self.primaryKey.fields:
            raise ValueError(
                f"{type(self).__name__} requires an explicitly defined primary key."
            )
        return self

    @model_validator(mode="after")
    def _validate_foreign_keys_self_only(self) -> Self:
        """Ensures that all foreign keys reference only the same table
        (self-referencing)."""
        for fk in self.foreignKeys:
            if fk.reference.resource is not None:
                raise ValueError(
                    f"{type(self).__name__} only supports self-referencing foreign"
                    f" keys: found external reference to '{fk.reference.resource}'."
                )
        return self
