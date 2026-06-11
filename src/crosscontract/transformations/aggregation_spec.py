from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator


class LevelKeepSpec(BaseModel):
    """Level-based aggregation with per-ID exceptions."""

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
    """One column's aggregation directive, mirroring the `get_data` argument.

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
        """Disambiguate dict-shaped inputs, mirroring `get_data`'s validation.

        A dict carrying `keep` without `level` is rejected; a dict carrying
        `level` becomes a `LevelKeepSpec`; any other dict is a raw mapping
        passthrough.

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

    def to_arg(self) -> Any:
        """Return the primitive form accepted by `get_data`.

        Returns:
            Any: The `int`, `list`, or `dict` form the `get_data` aggregation
                argument expects.
        """
        if isinstance(self.root, LevelKeepSpec):
            return self.root.model_dump()
        return self.root


class AggregationSpec(RootModel[dict[str, ColumnAggregation]]):
    """Per-column aggregation directives, keyed by dimension column name.

    Mirrors the `aggregation` argument of `get_data`. Call `to_get_data_arg`
    to obtain the plain `dict` that argument expects.
    """

    def to_get_data_arg(self) -> dict[str, Any]:
        """Return the plain `dict` form accepted by `get_data`.

        Returns:
            dict[str, Any]: Each column mapped to its primitive aggregation
                directive (`int`, `list`, or `dict`).
        """
        return {col: ca.to_arg() for col, ca in self.root.items()}
