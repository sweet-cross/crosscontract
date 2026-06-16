from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from crosscontract.contracts.contracts.base_contract import CONTRACT_NAME_PATTERN

from .aggregation_spec import AggregationSpec

FILE_FORMAT = Literal["csv", "parquet"]


class FetchSpecMixin(BaseModel):
    """Mixin describing how to fetch a variable's data.

    Carries the row `filters` and per-column `aggregation` directives pushed
    down into `CrossDataVariable.get_data`. Both are declarative; the consumer
    splats `get_data_kwargs` into the call.
    """

    model_config = ConfigDict(extra="forbid")

    contract: str = Field(
        pattern=CONTRACT_NAME_PATTERN,
        max_length=100,
        description=(
            "A unique identifier for the data contract. Must consist only of "
            "lowercase alphanumeric characters, '.', '_', and '-'."
        ),
    )

    format: FILE_FORMAT = Field(
        default="csv",
        description=(
            "The file format to fetch the data in. Supported formats are 'csv' and "
            "'parquet'. Defaults to 'csv'."
        ),
    )

    filters: dict[str, list[Any]] = Field(
        default_factory=dict,
        description=(
            "Fetch-time row allow-list pushed down into "
            "`CrossDataVariable.get_data`. Keys are column names, values "
            "are allowed-value lists. May be omitted or left empty when no "
            "filtering is needed."
        ),
    )
    aggregation: AggregationSpec = Field(
        default_factory=dict,
        description=(
            "Per-column aggregation directives passed to "
            "`CrossDataVariable.get_data`. See `ColumnAggregation` for "
            "the four accepted forms. May be omitted or left empty when "
            "no aggregation is needed (the variable is fetched as-is)."
        ),
    )

    @property
    def get_data_kwargs(self) -> dict[str, Any]:
        """Fetch-shaping keyword arguments for `CrossDataVariable.get_data`.

        Splat into the call, supplying presentation arguments separately:

        ```python
        variable.get_data(**spec.get_data_kwargs, use_titles=True)
        ```

        Empty `filters` / `aggregation` collapse to `None` — the `get_data`
        bypass sentinel, which also matches its parameter defaults.
        `exclude_defaults=True` drops an empty `keep` so a bare `LevelKeepSpec`
        round-trips to `{"level": N}` and hits the plain level-mapping branch.

        This is the fetch-shaping subset only; presentation arguments
        (`columns`, `use_titles`, `value_col`, `agg_func`) remain the caller's
        responsibility.

        Returns:
            dict[str, Any]: `{"filters": ..., "aggregation": ...}`, each value
            the raw shape `get_data` expects, or `None` when unset.
        """
        aggregation = (
            {
                col: spec.model_dump(exclude_defaults=True)
                for col, spec in self.aggregation.items()
            }
            if self.aggregation
            else None
        )
        return {
            "filters": self.filters or None,
            "aggregation": aggregation,
        }
