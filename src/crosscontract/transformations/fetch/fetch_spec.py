from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .aggregation_spec import AggregationSpec


class FetchSpecMixin(BaseModel):
    """Mixin for fetch specifications, which share the same structure as the
    `aggregation` argument of `get_data`."""

    model_config = ConfigDict(extra="forbid")

    filters: dict[str, list[Any]] = Field(
        description=(
            "Fetch-time row allow-list pushed down into "
            "`CrossDataVariable.get_data`. Keys are column names, values "
            "are allowed-value lists."
        ),
    )
    aggregation: AggregationSpec = Field(
        default_factory=dict,
        description=(
            "Per-column aggregation directives passed to "
            "`CrossDataVariable.get_data`. See `ColumnAggregation` for "
            "the four accepted forms. May be omitted or left empty when "
            "no aggregation is needed (the variable is fetched as-is); "
            "in that case `aggregation_for_get_data()` returns `None`."
        ),
    )
