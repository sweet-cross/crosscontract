from typing import Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from crosscontract.transformations.transformation import TransformationUnion

from .target import Target


class ExtractionInstructions(BaseModel):
    """How a submission bundle is split into per-contract datasets.

    Attributes:
        routing_column (str): The column whose value selects a target.
        transformation_profiles (dict[str, list[TransformationUnion]]): Named,
            reusable transformation sequences referenced by targets.
        targets (list[Target]): One entry per dataset extracted from the bundle.
    """

    model_config = ConfigDict(extra="forbid")
    routing_column: str = Field(
        ...,
        description=(
            "The name of the column in the submission data that is used to route "
            "the data to the appropriate target. I.e., this is used to filter the "
            "data out of the submission bundle and into the appropriate target for "
            "validation. "
        ),
    )

    transformation_profiles: dict[str, list[TransformationUnion]] = Field(
        default_factory=dict,
        description=(
            "A dictionary of transformation profiles, where the keys are the names "
            "of the profiles and the values are lists of transformations to apply. "
            "Transformation profiles are sets of transformations that can be  "
            "applied to multiple targets. If a target specifies a transformation "
            "profile, the transformations in that profile will be applied to the "
            "data before any other transformations specified in the target."
        ),
    )

    targets: list[Target] = Field(
        ...,
        description=(
            "A list of targets, where each target specifies the filters, "
            "transformations, and contract to be used to validate the extracted "
            "data."
        ),
        min_length=1,
    )

    @field_validator("targets", mode="before")
    @classmethod
    def _derive_filter_from_name(cls, targets: Any, info: ValidationInfo) -> Any:
        """If `filters` is not provided, derive it from the target name as
        `{routing_column: name}`.

        Only an omitted `filters` key is derived; an explicitly null one is left
        for pydantic to reject. The name is stripped here to match the
        `strip_whitespace` constraint applied to `Target.name`, which runs after
        this validator — otherwise the stored name and the derived routing value
        could differ.

        Input that is not the expected shape is handed on untouched, so pydantic
        reports it rather than this validator failing on raw data.

        Args:
            targets (Any): The raw `targets` input, before validation.
            info (ValidationInfo): Carries the fields validated so far.

        Returns:
            Any: The input with a derived `filters` wherever the key was omitted.
        """
        routing_column = info.data.get("routing_column")
        if routing_column is None or not isinstance(targets, list):
            return targets

        expanded = []
        for target in targets:
            if (
                isinstance(target, dict)
                and "filters" not in target
                and isinstance(target.get("name"), str)
            ):
                target = {**target, "filters": {routing_column: target["name"].strip()}}
            expanded.append(target)
        return expanded

    @model_validator(mode="after")
    def _check_contract_unique(self) -> Self:
        """Check that each contract is appearing at most once in the targets list.
        Raise if a contract is repeated.

        Returns:
            Self: The validated instance of ExtractionInstructions.

        Raises:
            ValueError: If a contract is repeated in the targets list.
        """
        contract_names = [target.contract for target in self.targets]
        duplicates = {name for name in contract_names if contract_names.count(name) > 1}
        if duplicates:
            raise ValueError(
                f"Duplicate contracts found in targets: {', '.join(sorted(duplicates))}"
            )
        return self

    @model_validator(mode="after")
    def _check_name_unique(self) -> Self:
        """Check that each target name is unique in the targets list.
        Raise if a name is repeated.

        Returns:
            Self: The validated instance of ExtractionInstructions.

        Raises:
            ValueError: If a name is repeated in the targets list.
        """
        names = [target.name for target in self.targets]
        duplicates = {name for name in names if names.count(name) > 1}
        if duplicates:
            raise ValueError(
                "Duplicate target names found in targets: "
                f"{', '.join(sorted(duplicates))}"
            )
        return self

    @model_validator(mode="after")
    def _check_transformation_profiles(self) -> Self:
        """Check that transformation profiles are defined for all targets that
        specify them. Raise if a target specifies a transformation profile that is
        not defined in the `transformation_profiles` dictionary.

        Returns:
            Self: The validated instance of ExtractionInstructions.

        Raises:
            ValueError: If a target specifies a transformation profile that is not
                defined.
        """
        defined_profiles = set(self.transformation_profiles.keys())
        referenced_profiles = {
            target.transformation_profile
            for target in self.targets
            if target.transformation_profile
        }
        undefined_profiles = referenced_profiles - defined_profiles
        if undefined_profiles:
            raise ValueError(
                f"Undefined transformation profiles referenced in targets: "
                f"{', '.join(undefined_profiles)}"
            )
        return self
