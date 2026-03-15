from typing import Any, Self

import pandas as pd

from crosscontract import CrossClient
from crosscontract.crossclient.services import ContractResource

from .base_variable import CrossBaseVariable
from .dimension import CrossDimension


class CrossDataVariable(CrossBaseVariable):
    """A variable obtained from the CROSS data platform"""

    def __init__(
        self,
        contract_resource: ContractResource,
        filters: dict[str, Any] | None = None,
    ):
        """Initialized a data variable with the given contract resource and filters.

        Args:
            contract_resource: The contract resource associated with this variable.
            filters: Additional filters to apply when fetching data (optional).
        """

        super().__init__(contract_resource=contract_resource)
        self._filters = filters
        # a dictionary with the references for each dimension, keyed by the name
        # of the column referring to the dimension (i.e. the foreign key column name)
        self._dimensions: dict[str, CrossDimension] = {}

    @classmethod
    def from_client(
        cls,
        client: CrossClient,
        contract_name: str,
        filters: dict[str, Any] | None = None,
    ) -> Self:
        """Build from a contract fetched via the client.

        Value variables can have filters applied when they are created, which
        will be applied to all data fetched for that variable.

        Args:
            client: An instance of CrossClient to fetch contract details.
            contract_name: The name of the contract to fetch.
            filters: Additional filters to apply when fetching data (optional).
        """
        cr = client.contracts.get(contract_name)
        return cls(contract_resource=cr, filters=filters)

    def __repr__(self) -> str:
        return f"CrossDataVariable(name={self.name}, filters={self._filters})"

    @property
    def dimensions(self) -> dict[str, CrossDimension]:
        """Get the dimensions associated with this variable. The keys of the returned
        dictionary are the names of the columns in this variable that refer to
        dimensions (i.e. the foreign key column names), and the values are the
        corresponding CrossDimension variables.

        Returns:
            dict[str, CrossDimension]: A dictionary mapping foreign key column names to
                CrossDimension variables.
        """
        return self._dimensions.copy()

    def add_dimension(self, item: CrossDimension):
        """Add a dimension variable to the registry, keyed by the referring
        foreign key column name(s).

        Args:
            item (CrossDimension): The CrossDimension variable to add.

        """
        if item in self._dimensions.values():
            return

        matching_fks = [
            fk for fk in self.foreign_keys if fk.reference.resource == item.name
        ]
        if not matching_fks:
            raise ValueError(
                f"No foreign key in '{self.name}' references dimension '{item.name}'. "
                f"Available foreign keys: {self.foreign_keys}"
            )
        for fk in matching_fks:
            if len(fk.fields) != 1:
                raise ValueError(
                    f"Foreign key referencing '{item.name}' has multiple fields: "
                    f"{fk.fields}. Only single-column foreign keys are supported."
                )
            # add to dimensions under the name of the referring column
            ref_column = fk.fields[0]
            existing_dimension = self._dimensions.get(ref_column)
            if existing_dimension is not None and existing_dimension is not item:
                raise ValueError(
                    "Ambiguous foreign key mapping for column "
                    f"'{ref_column}' in '{self.name}': already mapped to "
                    f"dimension '{existing_dimension.name}', cannot also map to "
                    f"'{item.name}'."
                )
            self._dimensions[ref_column] = item

    def _fetch_data(self) -> pd.DataFrame:
        """Fetch the data for this variable from the CROSS platform. The data
        is filtered according to the filters specified when the variable was
        created.

        Returns:
            pd.DataFrame: A DataFrame containing the results for the specified contract.
        """
        filters = self._filters
        df = self.contract_resource.get_data(filters=filters)
        return df

    @staticmethod
    def _get_filter_mask(df: pd.DataFrame, **filters: list[Any] | None) -> pd.Series:
        """Construct a boolean mask for filtering the DataFrame based on the
        provided filters.

        Args:
            df (pd.DataFrame): The DataFrame to filter.
            **filters (list[Any] | None): Keyword arguments with column name as the
                argument name and a list of allowed values for that column as the value.
                For example, `year=[2020, 2021]` will filter the DataFrame to include
                only rows where the 'year' column has values 2020 or 2021. If a filter
                value is None, it will be ignored (i.e., no filtering will be applied
                for that column).

        Returns:
            pd.Series: A boolean Series that can be used to filter the DataFrame.
        """
        # check that all filter keys are valid columns in the dataframe
        invalid = set(filters) - set(df.columns)
        if invalid:
            raise KeyError(
                f"Invalid filter columns: {invalid}. Valid columns are: "
                f"{df.columns.tolist()}"
            )

        mask = pd.Series(True, index=df.index)
        for column, values in filters.items():
            if values is not None:
                mask &= df[column].isin(values)
        return mask

    def _relabel_column_with_title(self, df: pd.DataFrame, column: str) -> pd.DataFrame:
        """Replace the ids in the specified column with the corresponding titles
        from the dimension.

        Args:
            df: The DataFrame containing the column to relabel.
            column: The name of the column to relabel.

        Returns:
            A DataFrame with the specified column relabeled with titles.
        """
        dimension = self.dimensions.get(column)
        if dimension is None:
            return df
        label_map = dimension.label_map
        df_out = df.copy()
        df_out[column] = df_out[column].map(label_map).fillna(df_out[column])
        return df_out

    @staticmethod
    def _aggregate(
        df: pd.DataFrame,
        dimension_col: str,
        dimension_map: dict[Any, Any],
        value_col: str = "value",
        agg_func: str = "sum",
    ) -> pd.DataFrame:
        """Aggregate data using a dimension value mapping.

        This helper is used by the public `get_data` method to aggregate rows after
        remapping values in ``dimension_col`` according to ``dimension_map``. The
        mapping can represent arbitrary groupings (for example, hierarchy levels,
        explicit ID lists, or custom value-to-group mappings).

        Args:
            df (pd.DataFrame): The DataFrame containing the data to aggregate.
            dimension_col (str): The name of the dimension column whose values will
                be remapped before grouping.
            dimension_map (dict[Any, Any]): Mapping from original dimension values
                to target aggregation values. Values not present in the mapping
                are left unchanged.
            value_col: The name of the column containing the values to aggregate.
            agg_func: The aggregation function to use (e.g., "sum", "mean").
        """
        agg_cols = [c for c in df.columns if c != value_col]
        df_out = (
            df.assign(  # is already copy
                **{
                    dimension_col: df[dimension_col]
                    .map(dimension_map)
                    .fillna(df[dimension_col])
                }
            )
            .groupby(agg_cols, as_index=False)[value_col]
            .agg(agg_func)
        )
        return df_out

    def _get_level_mapping(self, col: str, level: int) -> dict[Any, Any]:
        """Get the mapping for aggregating a dimension column to a specified level.

        Args:
            col (str): The name of the dimension column to aggregate.
            level (int): The hierarchy level to aggregate to.

        Returns:
            dict[Any, Any]: A dictionary mapping original dimension IDs to their
            aggregated IDs at the specified level.
        """
        dim = self.dimensions.get(col)

        if dim is None:  # pragma: no cover
            # defensive: already checked in _get_aggregation_mapping
            raise KeyError(
                f"Aggregation specified for column '{col}', but it is not a "
                "registered dimension foreign key. Available dimensions: "
                f"{list(self.dimensions.keys())}"
            )
        dim_map = dim.ancestor_maps.get(level)
        if dim_map is None:
            return {}  # level beyond max depth, no aggregation
        return dim_map

    def _get_ids_mapping(self, col: str, target_ids: list[Any]) -> dict[Any, Any]:
        """Get the mapping for aggregating a dimension column to a specified set of
        target IDs.

        Args:
            col (str): The name of the dimension column to aggregate.
            target_ids (list[Any]): A list of dimension IDs to aggregate to. Each
            original ID will
            be mapped to the nearest ancestor in this list. IDs already in the list
            map to themselves. IDs with no ancestor in the list are left unmapped.

        Returns:
            dict[Any, Any]: A dictionary mapping original dimension IDs to their
            aggregated IDs.
        """
        if col not in self.dimensions:  # pragma: no cover
            # defensive: already checked in _get_aggregation_mapping
            raise KeyError(
                f"Aggregation specified for column '{col}', but it is not a "
                "registered dimension foreign key. Available dimensions: "
                f"{list(self.dimensions.keys())}"
            )
        dim = self.dimensions[col]
        return dim.get_ancestor_map_by_ids(target_ids)

    def _get_aggregation_mapping(
        self,
        aggregation_spec: dict[str, int | list[Any] | dict[Any, Any]],
    ) -> dict[str, dict[Any, Any]]:
        """Build aggregation mappings from a user-facing aggregation specification.

        Translates the per-column aggregation specifications into concrete
        dictionaries that map original dimension values to their aggregated
        counterparts.  The returned mappings are consumed by ``_aggregate``.

        Each column in *aggregation_spec* accepts one of four forms:

        ``int`` - Aggregate to a hierarchy level.
            Every node is mapped to its ancestor at the given level via
            the dimension's precomputed ancestor maps.

            Example::

                {"region": 1}

        ``list[Any]`` - Aggregate to a target set of IDs.
            Every node is mapped to its nearest ancestor that appears in
            the provided list.  Nodes already in the list map to
            themselves.  Nodes with no ancestor in the set are left
            unmapped (kept as-is by ``_aggregate`` via ``fillna``).

            Example::

                {"region": ["cat_a", "cat_b"]}

        ``dict`` **with spec keys** (``"level"``, ``"keep"``) -
            Level-based aggregation with exceptions.

            * ``"level"`` (``int``, required): the hierarchy level to
            aggregate to.
            * ``"keep"`` (``list[Any]``, optional): IDs that are exempt
            from the level-based roll-up and map to themselves.

            Example::

                {"region": {"level": 0, "keep": ["cat_a"]}}

        ``dict`` **without spec keys** - Raw mapping passthrough.
            The dictionary is used as-is.  Unmapped IDs are kept
            unchanged by ``_aggregate`` (via ``fillna``).

            Example::

                {"region": {"leaf_1": "group_x", "leaf_2": "group_x"}}

        Args:
            aggregation_spec: Per-column aggregation specifications.  Keys
                are column names that correspond to registered dimension
                foreign keys (for level / ids modes) or arbitrary columns
                (for raw mapping mode).  Values are one of the four forms
                described above.

        Returns:
            A dictionary keyed by column name whose values are mappings
            from original dimension values to aggregated dimension values.

        Raises:
            TypeError: If a column specification is not ``int``, ``list``,
                or ``dict``.
            ValueError: If a spec-dict uses ``"keep"`` without ``"level"``.
            KeyError: If level-based or id-based aggregation is requested
                for a column that is not a registered dimension.
        """
        spec_keys = {"level", "keep"}

        mapping: dict[str, dict[Any, Any]] = {}
        for col, spec in aggregation_spec.items():
            if col not in self.dimensions:
                raise KeyError(
                    f"Aggregation specified for column '{col}', but it is not a "
                    "registered dimension foreign key. Available dimensions: "
                    f"{list(self.dimensions.keys())}"
                )
            # aggregation to single hierarchical level
            if isinstance(spec, int):
                dim_map = self._get_level_mapping(col, spec)

            # aggregation to specified set of IDs
            elif isinstance(spec, list):
                dim_map = self._get_ids_mapping(col, spec)

            # aggregation to level with exceptions for sub-categories
            elif isinstance(spec, dict) and spec.keys() & spec_keys:
                if "keep" in spec and "level" not in spec:
                    raise ValueError(
                        f"Aggregation spec for '{col}' has 'keep' without "
                        "'level'. 'keep' is only valid together with 'level'. "
                        "If you want to specify IDs to aggregate to without using "
                        " levels, use a list of IDs as the specification instead."
                    )
                elif "level" in spec and "keep" not in spec:
                    # treat as regular level-based aggregation if no exceptions
                    dim_map = self._get_level_mapping(col, spec["level"])
                else:
                    # aggregation to level with exceptions for sub-categories
                    # combine the level-based mapping with the exceptions specified in
                    # "keep" and use the id based mapping logic to map to the nearest
                    # ancestor in the combined set of target IDs
                    # 1. get the level-based mapping by id
                    level_map = self._get_level_mapping(col, spec["level"])
                    # 2. combine the level-based targets with the "keep" exceptions
                    #    to get the full list of target IDs for id-based aggregation
                    target_ids = list(
                        set(level_map.values()) | set(spec.get("keep", []))
                    )
                    # 3. call the mapping logic for id-based aggregation with
                    #    the combined target set
                    dim_map = self._get_ids_mapping(col, target_ids)

            elif isinstance(spec, dict):
                dim_map = spec

            else:
                raise TypeError(
                    f"Invalid aggregation spec for '{col}': expected int, "
                    f"list, or dict, got {type(spec).__name__}."
                )

            mapping[col] = dim_map

        return mapping

    def get_data(
        self,
        filters: dict[str, list[Any]] | None = None,
        columns: list[str] | None = None,
        use_titles: bool = False,
        aggregation: dict[str, int | list[Any] | dict[Any, Any]] | None = None,
        value_col: str = "value",
        agg_func: str = "sum",
    ) -> pd.DataFrame:
        """Get the data for this variable, optionally filtered and aggregated.

        This is the main public interface for retrieving data. It applies
        filtering, aggregation, title relabeling, and column selection in
        that order. Can be overridden in subclasses to add additional
        processing.

        Args:
            filters: Additional filters applied on top of any filters
                specified at variable creation time. Keys are column names,
                values are lists of allowed values for those columns.
            columns: Columns to include in the returned DataFrame. If
                ``None``, all columns are included. Applied last, after
                all other transformations.
            use_titles: If ``True``, replace IDs in dimension foreign key
                columns with the corresponding human-readable labels from
                the dimension's ``label_map``.
            aggregation: Per-column aggregation specifications. Keys are
                dimension foreign key column names. Values control how
                that dimension is aggregated and accept four forms:

                ``int`` — Aggregate to a hierarchy level::

                    # roll up to level 1 (categories)
                    var.get_data(aggregation={"region": 1})

                ``list[Any]`` — Aggregate to a target set of IDs. Each
                node maps to its nearest ancestor in the list::

                    # aggregate to specific nodes
                    var.get_data(aggregation={"region": ["cat_a", "cat_b"]})

                ``dict`` with ``"level"`` and optional ``"keep"`` — Level-
                based aggregation with exceptions. Nodes under a kept ID
                aggregate to that ID instead of rolling up to the level
                target::

                    # roll up to total, but preserve cat_a breakdown
                    var.get_data(
                        aggregation={"region": {"level": 0, "keep": ["cat_a"]}}
                    )

                ``dict`` without spec keys — Raw mapping passthrough.
                Keys are original IDs, values are target IDs. Unmapped
                IDs are kept as-is::

                    var.get_data(
                        aggregation={"region": {"leaf_1": "x", "leaf_2": "x"}}
                    )

                Aggregations are applied sequentially in the order they
                appear in the dictionary.
            value_col: The column containing numeric values to aggregate.
            agg_func: The aggregation function (e.g., ``"sum"``,
                ``"mean"``).

        Returns:
            A DataFrame with the requested filters, aggregations, title
            relabeling, and column selection applied.
        """
        df = self.data  # is already copy
        if filters:
            mask = self._get_filter_mask(df, **filters)
            df = df[mask]

        if aggregation is not None:
            agg_mappings = self._get_aggregation_mapping(aggregation)
            for col, dim_map in agg_mappings.items():
                df = self._aggregate(
                    df,
                    dimension_col=col,
                    dimension_map=dim_map,
                    value_col=value_col,
                    agg_func=agg_func,
                )
        if use_titles:
            cols = [c for c in df.columns if self.dimensions.get(c) is not None]
            for c in cols:
                df = self._relabel_column_with_title(df, c)
        if columns is not None:
            df = df[columns]
        return df
