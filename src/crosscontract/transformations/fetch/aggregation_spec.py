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

        A dict carrying `level` becomes a `LevelKeepSpec`; any other dict is a
        raw mapping passthrough. Invalid combinations (e.g. `keep` without
        `level`) are rejected by `get_data` at execution time.
        """
        if isinstance(v, dict) and "level" in v:
            return LevelKeepSpec.model_validate(v)
        return v


AggregationSpec = dict[str, ColumnAggregation]
