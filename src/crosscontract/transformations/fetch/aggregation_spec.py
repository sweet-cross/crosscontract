from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator


class LevelKeepSpec(BaseModel):
    """Level-based aggregation with exceptions."""

    model_config = ConfigDict(extra="forbid")

    level: int = Field(description="Hierarchy level to aggregate to.")
    keep: list[Any] = Field(
        default_factory=list,
        description=(
            "IDs exempt from the level roll-up; they map to themselves "
            "instead of rolling up."
        ),
    )


class ColumnAggregation(RootModel[int | list[Any] | LevelKeepSpec | dict[Any, Any]]):
    """One column's aggregation directive, accepted by `get_data`.

    Four forms:

    - `int` — roll up to a hierarchy level.
    - `list` — aggregate to a target set of IDs.
    - `LevelKeepSpec` (a dict with `level` and optional `keep`) — level-based
      roll-up with exceptions.
    - `dict` without spec keys — raw mapping passthrough.
    """

    @model_validator(mode="before")
    @classmethod
    def _pick_dict_form(cls, v: Any) -> Any:
        """Disambiguate dict-shaped inputs.

        A dict carrying `level` becomes a `LevelKeepSpec`; a dict carrying
        `keep` without `level` is rejected (mirroring `get_data`); any other
        dict is a raw mapping passthrough.

        Raises:
            ValueError: When `keep` is given without `level`.
        """
        if isinstance(v, dict):
            if "keep" in v and "level" not in v:
                raise ValueError(
                    "'keep' is only valid together with 'level'. To aggregate "
                    "to a target set of IDs, use a list of IDs instead."
                )
            if "level" in v:
                return LevelKeepSpec.model_validate(v)
        return v


AggregationSpec = dict[str, ColumnAggregation]
