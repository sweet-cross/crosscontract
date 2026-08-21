from pydantic import BaseModel, ConfigDict, Field

from crosscontract.contracts.contracts.base_contract import CONTRACT_NAME_PATTERN
from crosscontract.transformations.transformation import TransformationUnion


class Target(BaseModel):
    """A target is tabular data that is extracted from the batch of submission data,
    transformed, and validated against a data contract.

    The target is defined by a set of filters that are applied to the source data,
    a set of transformations that are applied to the filtered data before validation,
    and the contract against which the transformed data is validated.
    """

    model_config = ConfigDict(extra="forbid")

    filters: dict[str, str] = Field(
        ...,
        description=(
            "Filters to apply to the source data before applying transformations. "
            "A dictionary of key-value pairs to filter the source data. When "
            "authored inside `ExtractionInstructions`, a bare value is accepted as "
            "shorthand for a single filter on the routing column and expanded on "
            "load."
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
