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

    def test_repr_includes_name_and_filters(self, data_variable: CrossDataVariable):
        repr_str = repr(data_variable)
        assert "my_data" in repr_str
        assert "filters={'year': '2024'}" not in repr_str

        var_with_filters = CrossDataVariable(
            contract_resource=data_variable._contract_resource, filters={"year": "2024"}
        )
        repr_with_filters = repr(var_with_filters)
        assert "my_data" in repr_with_filters
        assert "filters={'year': '2024'}" in repr_with_filters


class TestAddDimension:
    def test_add_dimension(self, data_variable: CrossDataVariable, dimension):
        data_variable.add_dimension(dimension)
        assert "region" in data_variable.dimensions
        assert data_variable.dimensions["region"] is dimension

    def test_duplicate_dimension_is_noop(
        self, data_variable: CrossDataVariable, dimension
    ):
        data_variable.add_dimension(dimension)
        data_variable.add_dimension(dimension)
        assert data_variable.dimensions["region"] is dimension

    def test_no_matching_fk_raises(self, simple_variable, dimension):
        with pytest.raises(ValueError, match="No foreign key"):
            simple_variable.add_dimension(dimension)

    def test_multi_field_fk_raises(self, make_contract_resource, dimension):
        contract = {
            "name": "multi_fk_data",
            "description": "Composite FK",
            "title": "Multi FK",
            "tableschema": {
                "fields": [
                    {"name": "region", "type": "string"},
                    {"name": "region2", "type": "string"},
                    {"name": "value", "type": "number"},
                ],
                "foreignKeys": [
                    {
                        "fields": ["region", "region2"],
                        "reference": {"resource": "dim_region", "fields": ["id", "id"]},
                    }
                ],
            },
        }
        cr = make_contract_resource(data=var_no_fk_data, contract_dict=contract)
        var = CrossDataVariable(contract_resource=cr)
        with pytest.raises(ValueError, match="multiple fields"):
            var.add_dimension(dimension)

    def test_conflicting_dimension_for_same_column_raises(
        self, make_contract_resource, dimension
    ):
        """Two different dimensions both claiming the same FK column should raise."""
        cr = make_contract_resource(data=var_data, contract_dict=var_contract)
        var = CrossDataVariable(contract_resource=cr)
        var.add_dimension(dimension)

        # create a second, different dimension whose name also matches the FK reference
        other_dim_contract = {**dim_contract, "name": "dim_region"}
        other_cr = make_contract_resource(
            data=dim_data, contract_dict=other_dim_contract
        )
        other_dimension = CrossDimension(contract_resource=other_cr)

        # bypass the early return (different object, same resource name)
        with pytest.raises(ValueError, match="Ambiguous foreign key mapping"):
            var.add_dimension(other_dimension)


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


class TestAggregate:
    def test_basic_sum(self, data_variable: CrossDataVariable):
        df = data_variable.data
        dimension_map = {"leaf_1": "cat_a", "leaf_2": "cat_a", "leaf_3": "cat_b"}
        result = CrossDataVariable._aggregate(df, "region", dimension_map)
        row = result[(result["region"] == "cat_a") & (result["year"] == "2024")]
        assert row["value"].iloc[0] == 30.0  # 10 + 20

    def test_all_to_one(self, data_variable: CrossDataVariable):
        df = data_variable.data
        dimension_map = {"leaf_1": "total", "leaf_2": "total", "leaf_3": "total"}
        result = CrossDataVariable._aggregate(df, "region", dimension_map)
        assert (result["region"] == "total").all()
        row_2025 = result[result["year"] == "2025"]
        assert row_2025["value"].iloc[0] == 600.0

    def test_mean_agg_func(self, data_variable: CrossDataVariable):
        df = data_variable.data
        dimension_map = {"leaf_1": "cat_a", "leaf_2": "cat_a", "leaf_3": "cat_b"}
        result = CrossDataVariable._aggregate(
            df, "region", dimension_map, agg_func="mean"
        )
        row = result[(result["region"] == "cat_a") & (result["year"] == "2024")]
        assert row["value"].iloc[0] == 15.0  # (10 + 20) / 2

    def test_unmapped_ids_kept_as_is(self, data_variable: CrossDataVariable):
        df = data_variable.data
        dimension_map = {"leaf_1": "cat_a", "leaf_2": "cat_a"}
        # leaf_3 not in map → fillna keeps it
        result = CrossDataVariable._aggregate(df, "region", dimension_map)
        assert "leaf_3" in result["region"].values

    def test_identity_map_preserves_data(self, data_variable: CrossDataVariable):
        df = data_variable.data
        dimension_map = {"leaf_1": "leaf_1", "leaf_2": "leaf_2", "leaf_3": "leaf_3"}
        result = CrossDataVariable._aggregate(df, "region", dimension_map)
        sort_cols = df.columns.tolist()
        pd.testing.assert_frame_equal(
            result.sort_values(sort_cols).reset_index(drop=True),
            df.sort_values(sort_cols).reset_index(drop=True),
        )

    def test_does_not_mutate_input(self, data_variable: CrossDataVariable):
        df = data_variable.data
        original_regions = df["region"].tolist()
        dimension_map = {"leaf_1": "cat_a", "leaf_2": "cat_a", "leaf_3": "cat_b"}
        _ = CrossDataVariable._aggregate(df, "region", dimension_map)
        assert df["region"].tolist() == original_regions

    def test_custom_value_col(self):
        df = pd.DataFrame({"region": ["a", "b", "c"], "amount": [1.0, 2.0, 3.0]})
        dimension_map = {"a": "x", "b": "x", "c": "y"}
        result = CrossDataVariable._aggregate(
            df, "region", dimension_map, value_col="amount"
        )
        row = result[result["region"] == "x"]
        assert row["amount"].iloc[0] == 3.0


class TestGetAggregationMapping:
    """Tests for _get_aggregation_mapping and _get_level_mapping."""

    # --- int (level-based) ---

    def test_int_level_1(self, data_variable_with_dim: CrossDataVariable):
        result = data_variable_with_dim._get_aggregation_mapping({"region": 1})
        assert result["region"]["leaf_1"] == "cat_a"
        assert result["region"]["leaf_2"] == "cat_a"
        assert result["region"]["leaf_3"] == "cat_b"

    def test_int_level_0(self, data_variable_with_dim: CrossDataVariable):
        result = data_variable_with_dim._get_aggregation_mapping({"region": 0})
        assert result["region"]["leaf_1"] == "total"
        assert result["region"]["cat_a"] == "total"

    def test_int_level_beyond_max_returns_empty(
        self, data_variable_with_dim: CrossDataVariable
    ):
        result = data_variable_with_dim._get_aggregation_mapping({"region": 99})
        assert result["region"] == {}

    def test_int_non_dimension_col_raises(
        self, data_variable_with_dim: CrossDataVariable
    ):
        with pytest.raises(KeyError, match="registered dimension foreign key"):
            data_variable_with_dim._get_aggregation_mapping({"year": 0})

    # --- list (target IDs) ---

    def test_list_delegates_to_get_ids_mapping(
        self, data_variable_with_dim: CrossDataVariable
    ):
        result = data_variable_with_dim._get_aggregation_mapping(
            {"region": ["cat_a", "cat_b"]}
        )
        # _get_ids_mapping is stubbed to return {}, just verify it's called
        assert "region" in result

    def test_list_non_dimension_col_raises(
        self, data_variable_with_dim: CrossDataVariable
    ):
        with pytest.raises(KeyError, match="registered dimension foreign key"):
            data_variable_with_dim._get_aggregation_mapping(
                {"non_dimension_col": ["2024"]}
            )

    # --- dict with spec keys (level + keep) ---

    def test_dict_level_only(self, data_variable_with_dim: CrossDataVariable):
        result = data_variable_with_dim._get_aggregation_mapping(
            {"region": {"level": 1}}
        )
        assert result["region"]["leaf_1"] == "cat_a"
        assert result["region"]["leaf_3"] == "cat_b"

    def test_dict_level_with_keep(self, data_variable_with_dim: CrossDataVariable):
        result = data_variable_with_dim._get_aggregation_mapping(
            {"region": {"level": 0, "keep": ["cat_a"]}}
        )
        # cat_a maps to itself despite level 0
        assert result["region"]["cat_a"] == "cat_a"
        # everything else rolls up to total
        assert result["region"]["cat_b"] == "total"
        assert result["region"]["leaf_3"] == "total"

    def test_dict_keep_without_level_raises(
        self, data_variable_with_dim: CrossDataVariable
    ):
        with pytest.raises(ValueError, match="'keep' without 'level'"):
            data_variable_with_dim._get_aggregation_mapping(
                {"region": {"keep": ["cat_a"]}}
            )

    # --- dict without spec keys (raw passthrough) ---

    def test_raw_dict_passthrough(self, data_variable_with_dim: CrossDataVariable):
        raw = {"leaf_1": "group_x", "leaf_2": "group_x"}
        result = data_variable_with_dim._get_aggregation_mapping({"region": raw})
        assert result["region"] is raw

    # --- invalid types ---

    def test_invalid_type_raises(self, data_variable_with_dim: CrossDataVariable):
        with pytest.raises(TypeError, match="expected int, list, or dict"):
            data_variable_with_dim._get_aggregation_mapping({"region": "invalid"})

    def test_keep_preserves_subtree(self, data_variable_with_dim: CrossDataVariable):
        """Leaves under a kept node should map to that node, not the level target."""
        result = data_variable_with_dim._get_aggregation_mapping(
            {"region": {"level": 0, "keep": ["cat_a"]}}
        )
        assert result["region"]["leaf_1"] == "cat_a"
        assert result["region"]["leaf_2"] == "cat_a"

    def test_keep_does_not_affect_other_subtrees(
        self, data_variable_with_dim: CrossDataVariable
    ):
        """Nodes outside the kept subtree still roll up to the level target."""
        result = data_variable_with_dim._get_aggregation_mapping(
            {"region": {"level": 0, "keep": ["cat_a"]}}
        )
        assert result["region"]["leaf_3"] == "total"
        assert result["region"]["cat_b"] == "total"
        assert result["region"]["total"] == "total"

    def test_keep_multiple_ids(self, data_variable_with_dim: CrossDataVariable):
        """Keeping both categories at level 0 is equivalent to level 1."""
        result = data_variable_with_dim._get_aggregation_mapping(
            {"region": {"level": 0, "keep": ["cat_a", "cat_b"]}}
        )
        by_level = data_variable_with_dim._get_aggregation_mapping({"region": 1})
        assert result["region"] == by_level["region"]

    def test_keep_leaf_node(self, data_variable_with_dim: CrossDataVariable):
        """Keeping a leaf at level 0 means that leaf maps to itself."""
        result = data_variable_with_dim._get_aggregation_mapping(
            {"region": {"level": 0, "keep": ["leaf_1"]}}
        )
        assert result["region"]["leaf_1"] == "leaf_1"
        assert result["region"]["leaf_2"] == "total"
        assert result["region"]["leaf_3"] == "total"

    def test_keep_at_same_level_as_target(
        self, data_variable_with_dim: CrossDataVariable
    ):
        """Keeping a node already at the target level is a no-op."""
        result_with_keep = data_variable_with_dim._get_aggregation_mapping(
            {"region": {"level": 1, "keep": ["cat_a"]}}
        )
        result_without = data_variable_with_dim._get_aggregation_mapping({"region": 1})
        assert result_with_keep["region"] == result_without["region"]


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


class TestGetDataWithAggregation:
    # --- int (level-based) ---

    def test_aggregation_via_get_data(self, data_variable_with_dim: CrossDataVariable):
        df = data_variable_with_dim.get_data(aggregation={"region": 1})
        regions = set(df["region"])
        assert regions == {"cat_a", "cat_b"}

    def test_level_0_sums_all(self, data_variable_with_dim: CrossDataVariable):
        df = data_variable_with_dim.get_data(aggregation={"region": 0})
        assert (df["region"] == "total").all()
        row_2024 = df[df["year"] == "2024"]
        assert row_2024["value"].iloc[0] == 60.0

    def test_level_beyond_max_returns_unchanged(
        self, data_variable_with_dim: CrossDataVariable
    ):
        df = data_variable_with_dim.get_data(aggregation={"region": 99})
        assert len(df) == 6

    def test_filter_then_aggregate(self, data_variable_with_dim: CrossDataVariable):
        df = data_variable_with_dim.get_data(
            filters={"year": ["2024"]}, aggregation={"region": 0}
        )
        assert len(df) == 1
        assert df["value"].iloc[0] == 60.0

    def test_aggregate_with_mean(self, data_variable_with_dim: CrossDataVariable):
        df = data_variable_with_dim.get_data(aggregation={"region": 1}, agg_func="mean")
        row = df[(df["region"] == "cat_a") & (df["year"] == "2024")]
        assert row["value"].iloc[0] == 15.0

    # --- list (target IDs) ---

    def test_list_aggregation(self, data_variable_with_dim: CrossDataVariable):
        df = data_variable_with_dim.get_data(aggregation={"region": ["cat_a", "cat_b"]})
        assert set(df["region"]) == {"cat_a", "cat_b"}
        row = df[(df["region"] == "cat_a") & (df["year"] == "2025")]
        assert row["value"].iloc[0] == 300.0  # 100 + 200

    def test_list_partial_target_keeps_unmapped(
        self, data_variable_with_dim: CrossDataVariable
    ):
        """Targeting only cat_a leaves cat_b subtree unmapped (kept as-is)."""
        df = data_variable_with_dim.get_data(aggregation={"region": ["cat_a"]})
        # leaf_1/leaf_2 aggregate to cat_a, leaf_3 stays as leaf_3
        assert "cat_a" in df["region"].values
        assert "leaf_3" in df["region"].values

    # --- dict with level + keep ---

    def test_keep_preserves_subtree_values(
        self, data_variable_with_dim: CrossDataVariable
    ):
        df = data_variable_with_dim.get_data(
            aggregation={"region": {"level": 0, "keep": ["cat_a"]}}
        )
        # cat_a subtree: leaf_1 + leaf_2 → cat_a
        row_cat_a_2024 = df[(df["region"] == "cat_a") & (df["year"] == "2024")]
        assert row_cat_a_2024["value"].iloc[0] == 30.0
        # cat_b subtree rolls up to total
        row_total_2024 = df[(df["region"] == "total") & (df["year"] == "2024")]
        assert row_total_2024["value"].iloc[0] == 30.0  # leaf_3 only

    def test_keep_leaf_aggregates_rest(self, data_variable_with_dim: CrossDataVariable):
        df = data_variable_with_dim.get_data(
            filters={"year": ["2024"]},
            aggregation={"region": {"level": 0, "keep": ["leaf_1"]}},
        )
        row_leaf = df[df["region"] == "leaf_1"]
        assert row_leaf["value"].iloc[0] == 10.0
        row_total = df[df["region"] == "total"]
        assert row_total["value"].iloc[0] == 50.0  # 20 + 30

    def test_keep_all_categories_equivalent_to_level(
        self, data_variable_with_dim: CrossDataVariable
    ):
        df_keep = data_variable_with_dim.get_data(
            aggregation={"region": {"level": 0, "keep": ["cat_a", "cat_b"]}}
        )
        df_level = data_variable_with_dim.get_data(aggregation={"region": 1})
        sort_cols = df_keep.columns.tolist()
        pd.testing.assert_frame_equal(
            df_keep.sort_values(sort_cols).reset_index(drop=True),
            df_level.sort_values(sort_cols).reset_index(drop=True),
        )

    # --- dict without spec keys (raw passthrough) ---

    def test_raw_mapping(self, data_variable_with_dim: CrossDataVariable):
        df = data_variable_with_dim.get_data(
            aggregation={"region": {"leaf_1": "x", "leaf_2": "x", "leaf_3": "y"}}
        )
        assert set(df["region"]) == {"x", "y"}
        row = df[(df["region"] == "x") & (df["year"] == "2024")]
        assert row["value"].iloc[0] == 30.0

    # --- combined with titles ---

    def test_aggregate_then_titles(self, data_variable_with_dim: CrossDataVariable):
        df = data_variable_with_dim.get_data(aggregation={"region": 1}, use_titles=True)
        assert set(df["region"]) == {"Category A", "Category B"}

    # --- combined with columns ---

    def test_aggregate_then_select_columns(
        self, data_variable_with_dim: CrossDataVariable
    ):
        df = data_variable_with_dim.get_data(
            aggregation={"region": 0}, columns=["region", "value"]
        )
        assert list(df.columns) == ["region", "value"]
        assert (df["region"] == "total").all()
