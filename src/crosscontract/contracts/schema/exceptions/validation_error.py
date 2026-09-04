import ast
import re
from collections.abc import Hashable
from typing import Any

import pandas as pd
import pandera.pandas as pa

# Checks built from the check classes report themselves as
#   Columns '<col>, <col>' in check '<label>' <what went wrong>.
# The leading column list both marks the failure as a key or reference violation
# and names the columns whose values belong in the report.
CHECK_COLUMNS_PATTERN = r"^Columns '(?P<columns>[^']*)' in check '"


class SchemaValidationError(Exception):
    def __init__(
        self,
        message: str,
        schema_errors: pa.errors.SchemaErrors | pa.errors.SchemaError | None = None,
    ):
        """Initialize SchemaValidationError with optional pandera schema errors.

        Args:
            message (str): The error message.
            schema_errors (pa.errors.SchemaErrors, optional): Pandera SchemaErrors
                exception to parse for detailed error information.
        """
        super().__init__(message)
        self.message = message
        self._schema_errors: pa.errors.SchemaErrors | None = (
            self._convert_schema_error(schema_errors) if schema_errors else None
        )
        self._parsed_errors: list[dict[Hashable, Any]] | None = None

    @staticmethod
    def _convert_schema_error(
        error: pa.errors.SchemaError | pa.errors.SchemaErrors,
    ) -> pa.errors.SchemaErrors:
        """Convert a single pandera SchemaError to a SchemaErrors object
        for consistent parsing."""
        match error:
            case pa.errors.SchemaErrors():
                return error
            case pa.errors.SchemaError():
                # Create a SchemaErrors object with a single error case
                converted = pa.errors.SchemaErrors(
                    schema=error.schema, schema_errors=[error], data=pd.DataFrame()
                )
                return converted
            case _:
                raise TypeError(
                    f"Expected SchemaError or SchemaErrors, got {type(error)}"
                )

    @property
    def errors(self) -> list[dict[Hashable, Any]]:
        """Lazy-loads and parses the error details."""
        if self._parsed_errors is None:  # pragma: no cover
            self._parsed_errors = self._parse_pandera_errors()
        return self._parsed_errors

    def to_list(self) -> list[dict[Hashable, Any]]:
        """Return the errors as a list of dictionaries.

        Useful for API responses (JSON serialization).
        Alias for .errors.
        """
        return self.errors

    def to_pandas(self) -> pd.DataFrame:  # pragma: no cover
        """Return the errors as a pandas DataFrame.

        Useful for client-side debugging in Jupyter Notebooks.
        """
        return pd.DataFrame(self.errors)

    def _parse_pandera_errors(self) -> list[dict[Hashable, Any]]:
        """Parse pandera SchemaErrors into a list of error details.

        Returns:
            list[dict[str, Any]]: A list of error details dictionaries.
        """
        if self._schema_errors is None:
            return []
        e = self._schema_errors
        df_failures: pd.DataFrame = e.failure_cases

        # 1. CLEAN TYPE COERCION ERROR: We only keep the rows that failed coercion,
        # but delete the redundant dtype errors (for the whole column)
        coercion_mask = df_failures["check"].str.startswith("coerce_dtype")
        coercion_failed_cols = df_failures[coercion_mask]["column"].unique()
        is_redundant_dtype = (df_failures["check"].str.startswith("dtype")) & (
            df_failures["column"].isin(coercion_failed_cols)
        )
        df_failures = df_failures[~is_redundant_dtype].copy()

        # 2 CLEAN REFERENCE ERRORS
        df_failures = self._parse_reference_errors(df_failures, data=e.data)

        # 3. Format for Output (JSON safe)
        df_errors = (
            df_failures.replace({float("nan"): None})
            .sort_values(by=["check", "index"])
            .to_dict(orient="records")
        )
        return df_errors

    def _parse_reference_errors(
        self, df_failures: pd.DataFrame, data: pd.DataFrame | None
    ) -> pd.DataFrame:
        """Parse pandera SchemaErrors related to foreign key violations by combining
        the error messages for multiple rows into a single message per reference
        violation.

        Note: The function relies on the columns being named in the check's
        message, in one of two shapes:
        "ForeignKeyError: ['col1', 'col2']" / "PrimaryKeyError: ['col1', 'col2']"
            as produced by the legacy adapter, or
        "Columns 'col1, col2' in check '<label>' ..."
            as produced by the check classes.

        Args:
            df_failure (pd.DataFrame): The DataFrame containing the pandera failure
                cases.
            data (pd.DataFrame | None): The original DataFrame that was validated.

        Returns:
            pd.DataFrame: DataFrame with combined reference error messages.
        """
        reference_errors = ["ForeignKeyError", "PrimaryKeyError"]

        # 1. Identify reference errors, in either the legacy adapter's naming or
        # the message shape the check classes produce. The latter is matched with
        # `re` rather than `str.contains`, which warns about the named group it
        # carries for `_extract_cols`.
        check_columns = re.compile(CHECK_COLUMNS_PATTERN)
        is_ref_error = df_failures["check"].str.contains(
            "|".join(reference_errors), regex=True
        ) | df_failures["check"].map(
            lambda value: check_columns.search(str(value)) is not None
        )
        df_refs = df_failures[is_ref_error].copy()
        # relax the type constraints on the dataframe as we collect all failure
        # cases
        df_others = df_failures[~is_ref_error]

        # relax the type constraints on the dataframe as we collect all failure cases
        df_refs["failure_case"] = df_refs["failure_case"].astype(object)
        df_others = df_others.astype(object)

        if df_refs.empty:
            return df_failures

        # 2. Remove duplicate rows per check type. We only need one row per check
        # and index to report the failure cases
        df_refs = df_refs.drop_duplicates(subset=["check", "index"]).copy()

        # 3. Lookup values of the failure cases from the original data
        for check_name in df_refs["check"].unique():
            target_cols = self._extract_cols(check_name)
            if not target_cols:  # pragma: no cover
                continue

            # Identify rows belonging to the current check
            mask = df_refs["check"] == check_name
            error_indices = df_refs.loc[mask, "index"]

            # Fetch the failure cases from the original data
            # that is only possible if the data are available which is not the
            # case for non-lazy validation where the error is raised immediately
            # upon the first failure and the data are not attached to the error object.
            if data is not None and not data.empty:
                try:
                    # Different handling for pandas and other backends could be
                    # implemented here
                    actual_values = self._lookup_values_pandas(
                        data, error_indices, target_cols
                    )

                    # Assign back to  the failure report
                    df_refs.loc[mask, "failure_case"] = pd.Series(
                        actual_values, index=df_refs.loc[mask].index
                    )
                    df_refs.loc[mask, "column"] = ", ".join(target_cols)
                except KeyError:  # pragma: no cover
                    # Fallback if indices/columns are missing (edge cases)
                    continue

        # 4. Recombine with non-reference errors and return
        df_out = pd.concat([df_others, df_refs], ignore_index=True)
        return df_out

    def _lookup_values_pandas(
        self, data: pd.DataFrame, indices: pd.Series, cols: list[str]
    ) -> list[Any]:
        """Fetch values from the original dataframe. Here it assumed that the
        original dataframe is a pandas DataFrame.

        Note: Implementations for other backends (e.g., Polars) would need to
            provide their own version of this method.

        Args:
            data (pd.DataFrame): The original DataFrame.
            indices (pd.Series): The indices of the rows to fetch.
            cols (list[str]): The columns to fetch.
        """
        subset = data.loc[indices, cols]

        # Handle potential index duplication in source data
        if len(subset) != len(indices):
            # is tested but coverage does not verify this branch
            subset = subset[~subset.index.duplicated(keep="first")]  # pragma: no cover

        # Return as list of strings/tuples
        out_list = list(subset.itertuples(index=False, name=None))
        return out_list

    @staticmethod
    def _extract_cols(check_name: str) -> list[str]:
        """Helper to parse list string from check name.

        Args:
            check_name (str): The name of the check containing the list string.

        Returns:
            list[str]: The parsed list of column names.
        """
        match = re.search(r"(\[.*?\])", str(check_name))
        # note: code is tested but coverage does not verify this branch
        if match:
            try:
                return ast.literal_eval(match.group(1))
            except (ValueError, SyntaxError):  # pragma: no cover
                pass
        match = re.search(CHECK_COLUMNS_PATTERN, str(check_name))
        if match:
            return [col.strip() for col in match.group("columns").split(",")]
        return []
