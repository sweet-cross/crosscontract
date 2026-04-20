from typing import ClassVar, Literal

from pydantic import Field

from ..schema import MandatoryField
from .base_dimension import BaseDimensionSchema


class FlexibleDimensionSchema(BaseDimensionSchema):
    """
    A flexible dimension schema that allows for user-defined fields while enforcing
    the presence of two mandatory fields:
        - label: A label that describes the dimension value, which can be used
            for display purposes.
        - description: A description of the item in the dimension

    - ForeignKey references:
        As every other dimension, the flexible dimension can only have a self-reference
        but cannot enforce any other references.
    - PrimaryKey:
        The flexible dimension must have a primary key. The key can be a single
        field or a composite key, but it must be explicitly defined by the user.
    """

    _mandatory_fields: ClassVar[list[MandatoryField]] = [
        MandatoryField(
            name="label",
            type="string",
            description=(
                "A label that describes the dimension value, which can be used "
                "for display purposes."
            ),
        ),
        MandatoryField(
            name="description",
            type="string",
            description="A description of the item in the dimension.",
        ),
    ]

    # ignore type error as we want to enforce the table_type for this schema
    # for the pydantic discriminator to work correctly
    table_type: Literal["FlexibleDimension"] = Field(  # type: ignore[assignment]
        default="FlexibleDimension",
        description="Type of the table determines the structure of the schema.",
        exclude=True,
        repr=False,
    )
