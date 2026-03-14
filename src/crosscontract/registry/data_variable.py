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
        # a dictionary with the references for each dimension, keyed by dimension name
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
        """Get the dimensions associated with this variable."""
        return self._dimensions.copy()

    def add_dimension(self, item: CrossDimension):
        """Add a dimension variable to the registry."""
        if item.name in self._dimensions:
            raise ValueError(
                f"Dimension '{item.name}' already exists in the variable's dimensions."
            )
        self._dimensions[item.name] = item

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

    def _get_foreign_key_dimension(self, dimension_col: str) -> CrossDimension | None:
        """Get the dimension variable corresponding to a foreign key column.

        Args:
            dimension_col: The name of the column that is a foreign key reference
                to a dimension.

        Returns:
            The CrossDimension variable corresponding to the foreign key column.
            None in case no foreign key reference is found for the specified column.

        Raises:
            KeyError: If the specified column is not a foreign key or if the referenced
                dimension variable cannot be found in the registry.
        """
        fk_lst = [f for f in self.foreign_keys if f.fields == [dimension_col]]
        if not fk_lst:
            return None

        if len(fk_lst) > 1:
            raise KeyError(
                f"Multiple foreign keys found for column '{dimension_col}' "
                f"in variable '{self.name}'. "
                "Aggregation only allowed with a single foreign key reference. "
                f"Found foreign keys: {fk_lst}"
            )
        fk = fk_lst[0]
        dimension = self._dimensions.get(fk.reference.resource)
        if dimension is None:
            raise KeyError(
                f"Aggregation Error: Referenced dimension variable "
                f"'{fk.reference.resource}' not found in registry. "
                f"Available dimensions: {list(self.dimensions.keys())}"
            )
        return dimension

    def _relabel_column_with_title(self, df: pd.DataFrame, column: str) -> pd.DataFrame:
        """Replace the ids in the specified column with the corresponding titles
        from the dimension.

        Args:
            df: The DataFrame containing the column to relabel.
            column: The name of the column to relabel.

        Returns:
            A DataFrame with the specified column relabeled with titles.
        """
        dimension = self._get_foreign_key_dimension(column)
        if dimension is None:
            return df
        label_map = dimension.label_map
        df_out = df.copy()
        df_out[column] = df_out[column].map(label_map).fillna(df_out[column])
        return df_out

    def _aggregate_by_dimension(
        self,
        df: pd.DataFrame,
        agg_level: int,
        dimension_col: str,
        value_col: str = "value",
        agg_func: str = "sum",
    ) -> pd.DataFrame:
        """Aggregate data to a specified dimension level

        Args:
            df (pd.DataFrame): The DataFrame containing the data to aggregate.
            agg_level (int): The level of the dimension to aggregate to.
            dimension_col (str): The name of the dimension column to aggregate by.
            value_col (str, optional): The name of the column containing the values
                to aggregate.
                Defaults to "value".
            agg_func (str, optional): The aggregation function to use
                (e.g., "sum", "mean").
                Defaults to "sum".

        Returns:
            pd.DataFrame: A DataFrame containing the aggregated results.
        """
        dimension = self._get_foreign_key_dimension(dimension_col)
        if dimension is None:
            raise KeyError(
                f"Column '{dimension_col}' is not a foreign key reference to a "
                "dimension, or the referenced dimension variable is not available. "
                "Cannot perform aggregation. Available dimensions: "
                f"{list(self.dimensions.keys())}"
            )

        # get the mapping for the specified aggregation level
        mapping = dimension.ancestor_maps.get(agg_level)
        if mapping is None:
            # we have no mapping. likely the dimension is too deep. Thus, nothing
            # to aggregate, return the df as is
            return df

        # aggregate the values based on the mapping
        group_cols = [c for c in df.columns if c != value_col]
        df_out = (
            df.assign(
                **{
                    dimension_col: df[dimension_col]
                    .map(mapping)
                    .fillna(df[dimension_col])
                }
            )
            .groupby(group_cols, as_index=False)[value_col]
            .agg(agg_func)
        )
        return df_out

    def get_data(
        self,
        filters: dict[str, list[Any]] | None = None,
        columns: list[str] | None = None,
        use_titles: bool = False,
        aggregation: dict[str, int] | None = None,
        value_col: str = "value",
        agg_func: str = "sum",
    ) -> pd.DataFrame:
        """Public method to get the data for this variable. This can be overridden
        in subclasses to apply additional processing or filtering on top of the
        raw data fetched from the CROSS platform.

        Args:
            filters (dict[str, list[Any]], optional): Additional filters to apply
                to the data. This is a dictionary where keys are column names and
                values are lists of allowed values for those columns. This filtering
                is applied on top of any filters that were specified when the
                variable was created.
            columns (list[str], optional): A list of columns to include in the
                returned DataFrame.
                If None, all columns are included.
            use_titles (bool, optional): Whether to replace id used in columns
                referring to dimensions with the respective title from the dimension.
                Defaults to False.
            aggregation (dict[str, int], optional): A dictionary specifying how
                to aggregate the data. The key should be the name of the column/field
                to be aggregated, and the value should be the aggregation level
                to use for that column.
                Note that aggregations are applied sequentially in the order
                they are specified in the dictionary, and aggregation is only
                possible for columns that are foreign key references.
            value_col (str, optional): The name of the column containing the values
                to aggregate.
                Defaults to "value".
            agg_func (str, optional): The aggregation function to use
                (e.g., "sum", "mean").
                Defaults to "sum".
        """
        df = self.data  # is already copy
        if filters:
            mask = self._get_filter_mask(df, **filters)
            df = df[mask]
        for dim, agg_level in (aggregation or {}).items():
            df = self._aggregate_by_dimension(
                df,
                agg_level=agg_level,
                dimension_col=dim,
                value_col=value_col,
                agg_func=agg_func,
            )
        if use_titles:
            cols = [
                c for c in df.columns if self._get_foreign_key_dimension(c) is not None
            ]
            for c in cols:
                df = self._relabel_column_with_title(df, c)
        if columns is not None:
            df = df[columns]
        return df
