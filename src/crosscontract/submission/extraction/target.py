from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from crosscontract.contracts.contracts.base_contract import CONTRACT_NAME_PATTERN
from crosscontract.transformations.transformation import TransformationUnion


class Target(BaseModel):
    """A target is tabular data that is extracted from the batch of submission data,
    transformed, and validated against a data contract.

    The target is identified by its `name`, which is unique across the targets of a
    submission contract. It is further defined by a set of filters that are applied to
    the source data, a set of transformations that are applied to the filtered data
    before validation, and the contract against which the transformed data is
    validated.
    """

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = (
        Field(
            ...,
            description=(
                "The name of the target. This is used to identify the target in the "
                "extraction instructions. The name is unique in a submission "
                "contract. If no filter is provided, the name will be used as filter "
                "on the routing column."
            ),
        )
    )
    filters: dict[str, str] = Field(
        ...,
        description=(
            "Filters to apply to the source data before applying transformations. "
            "A dictionary of key-value pairs to filter the source data. When "
            "authored inside `ExtractionInstructions` and omitted entirely, it is "
            "derived as a single filter on the routing column using the target name."
        ),
    )
    contract: str = Field(
        ...,
        description="The contract against which the data is being validated. ",
        pattern=CONTRACT_NAME_PATTERN,
        max_length=100,
    )
    transformation_profile: str | None = Field(
        None,
        description=(
            "The name of the transformation profile to use for this target. "
            "If not provided, no transformation profile will be applied. The "
            "transformation profile is a set of transformations that are always "
            "applied before other transformations."
        ),
    )
    transformations: list[TransformationUnion] = Field(
        default_factory=list,
        description=(
            "The list of transformations to apply to the filtered data before "
            "validation."
        ),
    )
