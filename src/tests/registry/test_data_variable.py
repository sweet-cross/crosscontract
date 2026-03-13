# test_data_variable.py

import pandas as pd
import pytest

from crosscontract.registry import CrossDataVariable, CrossDimension

# ---------------------------------------------------------------------------
# Dimension contract & data (reused from test_dimensions)
# ---------------------------------------------------------------------------
dim_contract = {
    "name": "dim_region",
    "description": "A hierarchical dimension",
    "title": "Region",
    "tableschema": {
        "fields": [
            {"name": "id", "type": "string"},
            {"name": "label", "type": "string"},
            {"name": "level", "type": "integer"},
            {"name": "id_parent", "type": "string"},
        ],
    },
}

dim_data = pd.DataFrame(
    {
        "id": ["total", "cat_a", "cat_b", "leaf_1", "leaf_2", "leaf_3"],
        "label": ["Total", "Category A", "Category B", "Leaf 1", "Leaf 2", "Leaf 3"],
        "level": [0, 1, 1, 2, 2, 2],
        "id_parent": [None, "total", "total", "cat_a", "cat_a", "cat_b"],
    }
)

# ---------------------------------------------------------------------------
# Data variable contract & data
# ---------------------------------------------------------------------------
var_contract = {
    "name": "my_data",
    "description": "Test data variable",
    "title": "My Data",
    "tableschema": {
        "fields": [
            {"name": "region", "type": "string"},
            {"name": "year", "type": "string"},
            {"name": "value", "type": "number"},
        ],
        "foreignKeys": [
            {
                "fields": ["region"],
                "reference": {"resource": "dim_region", "fields": ["id"]},
            }
        ],
    },
}

var_data = pd.DataFrame(
    {
        "region": ["leaf_1", "leaf_2", "leaf_3", "leaf_1", "leaf_2", "leaf_3"],
        "year": ["2024", "2024", "2024", "2025", "2025", "2025"],
        "value": [10.0, 20.0, 30.0, 100.0, 200.0, 300.0],
    }
)

# Contract without foreign keys
var_no_fk_contract = {
    "name": "simple_data",
    "description": "No foreign keys",
    "title": "Simple",
    "tableschema": {
        "fields": [
            {"name": "category", "type": "string"},
            {"name": "value", "type": "number"},
        ],
    },
}

var_no_fk_data = pd.DataFrame(
    {
        "category": ["a", "b", "c"],
        "value": [1.0, 2.0, 3.0],
    }
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def dimension(make_contract_resource) -> CrossDimension:
    cr = make_contract_resource(data=dim_data, contract_dict=dim_contract)
    return CrossDimension(contract_resource=cr)


@pytest.fixture
def data_variable(make_contract_resource) -> CrossDataVariable:
    cr = make_contract_resource(data=var_data, contract_dict=var_contract)
    return CrossDataVariable(contract_resource=cr)


@pytest.fixture
def data_variable_with_dim(data_variable, dimension) -> CrossDataVariable:
    """Data variable with the region dimension already attached."""
    data_variable.add_dimension(dimension)
    return data_variable


@pytest.fixture
def simple_variable(make_contract_resource) -> CrossDataVariable:
    """Data variable without foreign keys."""
    cr = make_contract_resource(data=var_no_fk_data, contract_dict=var_no_fk_contract)
    return CrossDataVariable(contract_resource=cr)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestInit:
    def test_dimensions_empty_on_init(self, data_variable: CrossDataVariable):
        assert data_variable.dimensions == {}

    def test_filters_stored(self, make_contract_resource):
        cr = make_contract_resource(data=var_data, contract_dict=var_contract)
        var = CrossDataVariable(contract_resource=cr, filters={"year": "2024"})
        assert var._filters == {"year": "2024"}

    def test_no_filters_by_default(self, data_variable: CrossDataVariable):
        assert data_variable._filters is None


class TestAddDimension:
    def test_add_dimension(self, data_variable: CrossDataVariable, dimension):
        data_variable.add_dimension(dimension)
        assert "dim_region" in data_variable.dimensions
        assert data_variable.dimensions["dim_region"] is dimension

    def test_duplicate_dimension_rejected(
        self, data_variable: CrossDataVariable, dimension
    ):
        data_variable.add_dimension(dimension)
        with pytest.raises(ValueError, match="already exists"):
            data_variable.add_dimension(dimension)


class TestFetchData:
    def test_fetch_without_filters(self, data_variable: CrossDataVariable):
        df = data_variable.data
        pd.testing.assert_frame_equal(df, var_data)

    def test_fetch_with_filters(self, make_contract_resource):
        cr = make_contract_resource(data=var_data, contract_dict=var_contract)
        var = CrossDataVariable(contract_resource=cr, filters={"year": "2024"})
        # trigger lazy load
        _ = var.data
        # get_data should have been called with columns excluding "year" and the filter
        cr.get_data.assert_called_once_with(filters={"year": "2024"})


class TestGetFilterMask:
    def test_valid_filter(self, data_variable: CrossDataVariable):
        df = data_variable.data
        mask = CrossDataVariable._get_filter_mask(df, year=["2024"])
        assert mask.sum() == 3

    def test_multiple_filters(self, data_variable: CrossDataVariable):
        df = data_variable.data
        mask = CrossDataVariable._get_filter_mask(df, year=["2024"], region=["leaf_1"])
        assert mask.sum() == 1

    def test_invalid_column_raises(self, data_variable: CrossDataVariable):
        df = data_variable.data
        with pytest.raises(KeyError, match="Invalid filter columns"):
            CrossDataVariable._get_filter_mask(df, nonexistent=["x"])

    def test_none_value_skipped(self, data_variable: CrossDataVariable):
        df = data_variable.data
        mask = CrossDataVariable._get_filter_mask(df, year=None)
        # None means no filtering on that column
        assert mask.all()


class TestGetData:
    def test_basic(self, data_variable: CrossDataVariable):
        df = data_variable.get_data()
        pd.testing.assert_frame_equal(df, var_data)

    def test_returns_copy(self, data_variable: CrossDataVariable):
        df1 = data_variable.get_data()
        df2 = data_variable.get_data()
        assert df1 is not df2

    def test_with_filters(self, data_variable: CrossDataVariable):
        df = data_variable.get_data(filters={"year": ["2025"]})
        assert len(df) == 3
        assert (df["year"] == "2025").all()

    def test_with_columns(self, data_variable: CrossDataVariable):
        df = data_variable.get_data(columns=["region", "value"])
        assert list(df.columns) == ["region", "value"]

    def test_filters_and_columns(self, data_variable: CrossDataVariable):
        df = data_variable.get_data(
            filters={"year": ["2024"]}, columns=["region", "value"]
        )
        assert len(df) == 3
        assert "year" not in df.columns

    def test_does_not_mutate_cache(self, data_variable: CrossDataVariable):
        """Filtering in get_data must not alter the cached data."""
        _ = data_variable.get_data(filters={"year": ["2024"]})
        df_full = data_variable.get_data()
        assert len(df_full) == 6


class TestGetForeignKeyDimension:
    def test_returns_dimension(self, data_variable_with_dim: CrossDataVariable):
        dim = data_variable_with_dim._get_foreign_key_dimension("region")
        assert dim is not None
        assert dim.name == "dim_region"

    def test_returns_none_for_non_fk(self, data_variable_with_dim: CrossDataVariable):
        result = data_variable_with_dim._get_foreign_key_dimension("year")
        assert result is None

    def test_missing_dimension_raises(self, data_variable: CrossDataVariable):
        """FK exists but dimension not added to the variable."""
        with pytest.raises(KeyError, match="not found in registry"):
            data_variable._get_foreign_key_dimension("region")

    def test_no_fk_returns_none(self, simple_variable: CrossDataVariable):
        result = simple_variable._get_foreign_key_dimension("category")
        assert result is None

    def test_multiple_fks_for_same_column_raises(self, make_contract_resource):
        """If a column has multiple foreign key entries, _get_foreign_key_dimension
        raises."""
        contract_dict = {
            "name": "multi_fk",
            "description": "Multiple FKs on same field",
            "title": "Multi FK",
            "tableschema": {
                "fields": [
                    {"name": "region", "type": "string"},
                    {"name": "value", "type": "number"},
                ],
                "foreignKeys": [
                    {
                        "fields": ["region"],
                        "reference": {"resource": "dim_region", "fields": ["id"]},
                    },
                    {
                        "fields": ["region"],
                        "reference": {"resource": "dim_other", "fields": ["id"]},
                    },
                ],
            },
        }
        cr = make_contract_resource(data=var_data, contract_dict=contract_dict)
        var = CrossDataVariable(contract_resource=cr)
        with pytest.raises(KeyError, match="Multiple foreign keys found"):
            var._get_foreign_key_dimension("region")


class TestRelabelColumnWithTitle:
    def test_relabels_fk_column(self, data_variable_with_dim: CrossDataVariable):
        df = data_variable_with_dim.data
        result = data_variable_with_dim._relabel_column_with_title(df, "region")
        assert set(result["region"]) == {"Leaf 1", "Leaf 2", "Leaf 3"}

    def test_non_fk_column_unchanged(self, data_variable_with_dim: CrossDataVariable):
        df = data_variable_with_dim.data
        result = data_variable_with_dim._relabel_column_with_title(df, "year")
        pd.testing.assert_series_equal(result["year"], df["year"])

    def test_does_not_mutate_input(self, data_variable_with_dim: CrossDataVariable):
        df = data_variable_with_dim.data
        original_regions = df["region"].tolist()
        _ = data_variable_with_dim._relabel_column_with_title(df, "region")
        assert df["region"].tolist() == original_regions


class TestAggregateByDimension:
    def test_aggregate_to_level_1(self, data_variable_with_dim: CrossDataVariable):
        df = data_variable_with_dim.data
        result = data_variable_with_dim._aggregate_by_dimension(
            df, agg_level=1, dimension_col="region"
        )
        # leaf_1 + leaf_2 -> cat_a, leaf_3 -> cat_b, per year
        row_cat_a_2024 = result[
            (result["region"] == "cat_a") & (result["year"] == "2024")
        ]
        assert row_cat_a_2024["value"].iloc[0] == 30.0  # 10 + 20

        row_cat_b_2025 = result[
            (result["region"] == "cat_b") & (result["year"] == "2025")
        ]
        assert row_cat_b_2025["value"].iloc[0] == 300.0

    def test_aggregate_to_level_0(self, data_variable_with_dim: CrossDataVariable):
        df = data_variable_with_dim.data
        result = data_variable_with_dim._aggregate_by_dimension(
            df, agg_level=0, dimension_col="region"
        )
        # everything maps to "total"
        assert (result["region"] == "total").all()
        row_2024 = result[result["year"] == "2024"]
        assert row_2024["value"].iloc[0] == 60.0  # 10 + 20 + 30

    def test_aggregate_deep_level_returns_unchanged(
        self, data_variable_with_dim: CrossDataVariable
    ):
        """Aggregation level beyond max returns df as-is."""
        df = data_variable_with_dim.data
        result = data_variable_with_dim._aggregate_by_dimension(
            df, agg_level=99, dimension_col="region"
        )
        pd.testing.assert_frame_equal(result, df)

    def test_aggregate_non_fk_raises(self, data_variable_with_dim: CrossDataVariable):
        df = data_variable_with_dim.data
        with pytest.raises(KeyError, match="not a foreign key reference"):
            data_variable_with_dim._aggregate_by_dimension(
                df, agg_level=0, dimension_col="year"
            )

    def test_aggregate_with_mean(self, data_variable_with_dim: CrossDataVariable):
        df = data_variable_with_dim.data
        result = data_variable_with_dim._aggregate_by_dimension(
            df, agg_level=1, dimension_col="region", agg_func="mean"
        )
        row_cat_a_2024 = result[
            (result["region"] == "cat_a") & (result["year"] == "2024")
        ]
        assert row_cat_a_2024["value"].iloc[0] == 15.0  # (10 + 20) / 2


class TestGetDataWithAggregation:
    def test_aggregation_via_get_data(self, data_variable_with_dim: CrossDataVariable):
        df = data_variable_with_dim.get_data(aggregation={"region": 1})
        regions = set(df["region"])
        assert regions == {"cat_a", "cat_b"}

    def test_filter_then_aggregate(self, data_variable_with_dim: CrossDataVariable):
        df = data_variable_with_dim.get_data(
            filters={"year": ["2024"]}, aggregation={"region": 0}
        )
        assert len(df) == 1
        assert df["value"].iloc[0] == 60.0


class TestGetDataUseTitles:
    def test_use_titles_replaces_ids_with_labels(
        self, data_variable_with_dim: CrossDataVariable
    ):
        df = data_variable_with_dim.get_data(use_titles=True)
        assert set(df["region"]) == {"Leaf 1", "Leaf 2", "Leaf 3"}

    def test_use_titles_does_not_affect_non_fk_columns(
        self, data_variable_with_dim: CrossDataVariable
    ):
        df = data_variable_with_dim.get_data(use_titles=True)
        assert set(df["year"]) == {"2024", "2025"}

    def test_use_titles_does_not_mutate_cache(
        self, data_variable_with_dim: CrossDataVariable
    ):
        _ = data_variable_with_dim.get_data(use_titles=True)
        df = data_variable_with_dim.get_data(use_titles=False)
        assert set(df["region"]) == {"leaf_1", "leaf_2", "leaf_3"}


class TestFromClient:
    def test_from_client_with_filters(self, make_contract_resource):
        from unittest.mock import MagicMock

        cr = make_contract_resource(data=var_data, contract_dict=var_contract)
        client = MagicMock()
        client.contracts.get.return_value = cr

        var = CrossDataVariable.from_client(client, "my_data", filters={"year": "2024"})

        client.contracts.get.assert_called_once_with("my_data")
        assert var._filters == {"year": "2024"}
