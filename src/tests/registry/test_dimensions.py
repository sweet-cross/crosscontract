import numpy as np
import pandas as pd
import pytest

from crosscontract.registry import CrossDimension, CrossFlexibleDimension

# ---------------------------------------------------------------------------
# Test contract & data
# ---------------------------------------------------------------------------
# A simple 3-level hierarchy:
#
#   level 0:  total
#   level 1:  ├── cat_a
#             └── cat_b
#   level 2:  ├── leaf_1  (under cat_a)
#             ├── leaf_2  (under cat_a)
#             └── leaf_3  (under cat_b)
#
dim_contract = {
    "name": "dim_region",
    "description": "A hierarchical dimension",
    "title": "Region",
    "tableschema": {
        "primaryKey": ["id"],
        "fields": [
            {"name": "id", "type": "string"},
            {"name": "label", "type": "string"},
            {"name": "level", "type": "integer"},
            {"name": "parent_id", "type": "string"},
            {"name": "color", "type": "string"},
        ],
    },
}

dim_data = pd.DataFrame(
    {
        "id": ["total", "cat_a", "cat_b", "leaf_1", "leaf_2", "leaf_3"],
        "label": ["Total", "Category A", "Category B", "Leaf 1", "Leaf 2", "Leaf 3"],
        "level": [0, 1, 1, 2, 2, 2],
        "parent_id": [None, "total", "total", "cat_a", "cat_a", "cat_b"],
        "color": ["#FFFFFF", "#FF0000", "#00FF00", "#0000FF", "#FFFF00", "#00FFFF"],
    }
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def dimension(make_contract_resource) -> CrossDimension:
    cr = make_contract_resource(data=dim_data, contract_dict=dim_contract)
    return CrossDimension(contract_resource=cr)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestInit:
    def test_filters_rejected(self, make_contract_resource):
        cr = make_contract_resource(data=dim_data, contract_dict=dim_contract)
        with pytest.raises(TypeError):
            CrossDimension(contract_resource=cr, filters={"id": "total"})

    def test_str(self, dimension: CrossDimension):
        assert str(dimension) == "Dimension(name=dim_region)"


class TestLabelMap:
    def test_all_ids_mapped(self, dimension: CrossDimension):
        label_map = dimension.label_map
        assert label_map == {
            "total": "Total",
            "cat_a": "Category A",
            "cat_b": "Category B",
            "leaf_1": "Leaf 1",
            "leaf_2": "Leaf 2",
            "leaf_3": "Leaf 3",
        }

    def test_label_map_cached(self, dimension: CrossDimension):
        map1 = dimension.label_map
        map2 = dimension.label_map
        assert map1 == map2
        assert map1 is not map2  # copies returned


class TestColorMap:
    def test_all_colors_mapped(self, dimension: CrossDimension):
        color_map = dimension.color_map
        assert set(color_map.keys()) == set(dim_data["id"])
        for k, v in color_map.items():
            assert v == dim_data.loc[dim_data["id"] == k, "color"].iloc[0]

    def test_color_map_cached(self, dimension: CrossDimension):
        map1 = dimension.color_map
        map2 = dimension.color_map
        assert map1 == map2
        assert map1 is not map2  # copies returned

    def test_no_color_column(self, make_contract_resource):
        contract = {
            "name": "dim_no_color",
            "description": "Dimension without color column",
            "title": "No Color",
            "tableschema": {
                "primaryKey": ["id"],
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "label", "type": "string"},
                    {"name": "level", "type": "integer"},
                    {"name": "parent_id", "type": "string"},
                ],
            },
        }
        data = dim_data.drop(columns=["color"])
        cr = make_contract_resource(data=data, contract_dict=contract)
        dim = CrossDimension(contract_resource=cr)
        assert dim.color_map == {}

    @pytest.mark.parametrize("empty_value", ["", None, pd.NA, np.nan])
    def test_empty_color_values(self, make_contract_resource, empty_value):
        data = dim_data.copy()
        data["color"] = empty_value  # empty color values
        cr = make_contract_resource(data=data, contract_dict=dim_contract)
        dim = CrossDimension(contract_resource=cr)
        assert dim.color_map == {}


class TestAncestorMaps:
    def test_levels_present(self, dimension: CrossDimension):
        """Ancestor maps should have keys for levels 0 and 1 (range(max_level=2))."""
        assert set(dimension.ancestor_maps.keys()) == {0, 1}

    def test_level_0_maps_everything_to_root(self, dimension: CrossDimension):
        level_0 = dimension.ancestor_maps[0]
        for node_id in dim_data["id"]:
            assert level_0[node_id] == "total"

    def test_level_1_maps_leaves_to_categories(self, dimension: CrossDimension):
        level_1 = dimension.ancestor_maps[1]
        # leaves map to their parent category
        assert level_1["leaf_1"] == "cat_a"
        assert level_1["leaf_2"] == "cat_a"
        assert level_1["leaf_3"] == "cat_b"
        # categories and root map to themselves (already at level >= 1)
        assert level_1["cat_a"] == "cat_a"
        assert level_1["cat_b"] == "cat_b"
        assert level_1["total"] == "total"

    def test_ancestor_maps_cached(self, dimension: CrossDimension):
        maps1 = dimension.ancestor_maps
        maps2 = dimension.ancestor_maps
        assert maps1 == maps2
        assert maps1 is not maps2  # copies returned


class TestFlatDimension:
    """Edge case: a dimension with only one level (all at level 0)."""

    flat_contract = {
        "name": "dim_flat",
        "description": "A flat dimension",
        "title": "Flat",
        "tableschema": {
            "primaryKey": ["id"],
            "fields": [
                {"name": "id", "type": "string"},
                {"name": "label", "type": "string"},
                {"name": "level", "type": "integer"},
                {"name": "parent_id", "type": "string"},
            ],
        },
    }

    flat_data = pd.DataFrame(
        {
            "id": ["a", "b", "c"],
            "label": ["A", "B", "C"],
            "level": [0, 0, 0],
            "parent_id": [None, None, None],
        }
    )

    def test_no_ancestor_maps(self, make_contract_resource):
        cr = make_contract_resource(
            data=self.flat_data, contract_dict=self.flat_contract
        )
        dim = CrossDimension(contract_resource=cr)
        # range(0) produces nothing
        assert dim.ancestor_maps == {}

    def test_label_map_still_works(self, make_contract_resource):
        cr = make_contract_resource(
            data=self.flat_data, contract_dict=self.flat_contract
        )
        dim = CrossDimension(contract_resource=cr)
        assert dim.label_map == {"a": "A", "b": "B", "c": "C"}


class TestDataCaching:
    def test_data_cached(self, dimension: CrossDimension):
        df1 = dimension.data
        df2 = dimension.data
        assert df1.equals(df2)
        assert df1 is not df2  # copies returned

    def test_data_cache_independent(self, dimension: CrossDimension):
        df1 = dimension.data
        # Modifying the returned DataFrame should not affect the cached version
        df1["new_col"] = "test"
        df2 = dimension.data
        assert "new_col" not in df2.columns

    def test_clear_data_cache(self, dimension: CrossDimension):
        _ = dimension.data
        dimension.clear_data_cache()
        assert dimension._data is None
        assert dimension._ancestor_maps is None
        assert dimension._label_map is None
        _ = dimension.data
        assert dimension.contract_resource.get_data.call_count == 2


class TestAncestryChains:
    def test_leaf_chain(self, dimension: CrossDimension):
        chains = dimension._build_ancestry_chains()
        assert chains["leaf_1"] == ["leaf_1", "cat_a", "total"]

    def test_mid_level_chain(self, dimension: CrossDimension):
        chains = dimension._build_ancestry_chains()
        assert chains["cat_a"] == ["cat_a", "total"]

    def test_root_chain(self, dimension: CrossDimension):
        chains = dimension._build_ancestry_chains()
        assert chains["total"] == ["total"]

    def test_all_nodes_present(self, dimension: CrossDimension):
        chains = dimension._build_ancestry_chains()
        assert set(chains.keys()) == {
            "total",
            "cat_a",
            "cat_b",
            "leaf_1",
            "leaf_2",
            "leaf_3",
        }

    def test_cached_after_first_call(self, dimension: CrossDimension):
        _ = dimension.get_ancestor_map_by_ids(["total"])
        assert dimension._ancestry_chains is not None

    def test_cleared_with_cache(self, dimension: CrossDimension):
        _ = dimension.get_ancestor_map_by_ids(["total"])
        dimension.clear_data_cache()
        assert dimension._ancestry_chains is None


class TestGetAncestorMapByIds:
    def test_reuses_cached_chains(self, dimension: CrossDimension):
        """Second call skips _build_ancestry_chains (covers cached branch)."""
        _ = dimension.get_ancestor_map_by_ids(["total"])
        result = dimension.get_ancestor_map_by_ids(["cat_a", "cat_b"])
        assert result["leaf_1"] == "cat_a"

    def test_target_root(self, dimension: CrossDimension):
        result = dimension.get_ancestor_map_by_ids(["total"])
        for node_id in ["total", "cat_a", "cat_b", "leaf_1", "leaf_2", "leaf_3"]:
            assert result[node_id] == "total"

    def test_target_categories(self, dimension: CrossDimension):
        result = dimension.get_ancestor_map_by_ids(["cat_a", "cat_b"])
        assert result["leaf_1"] == "cat_a"
        assert result["leaf_2"] == "cat_a"
        assert result["leaf_3"] == "cat_b"
        assert result["cat_a"] == "cat_a"
        assert result["cat_b"] == "cat_b"

    def test_target_leaves(self, dimension: CrossDimension):
        result = dimension.get_ancestor_map_by_ids(["leaf_1", "leaf_2", "leaf_3"])
        assert result["leaf_1"] == "leaf_1"
        assert result["leaf_2"] == "leaf_2"
        assert result["leaf_3"] == "leaf_3"

    def test_mixed_levels(self, dimension: CrossDimension):
        result = dimension.get_ancestor_map_by_ids(["cat_a", "total"])
        assert result["leaf_1"] == "cat_a"
        assert result["leaf_2"] == "cat_a"
        assert result["cat_a"] == "cat_a"
        assert result["leaf_3"] == "total"
        assert result["cat_b"] == "total"

    def test_no_ancestor_in_target_omitted(self, dimension: CrossDimension):
        result = dimension.get_ancestor_map_by_ids(["cat_a"])
        assert "leaf_1" in result
        assert "cat_a" in result
        assert "leaf_3" not in result
        assert "cat_b" not in result
        assert "total" not in result

    def test_empty_target(self, dimension: CrossDimension):
        assert dimension.get_ancestor_map_by_ids([]) == {}

    def test_single_node(self, dimension: CrossDimension):
        assert dimension.get_ancestor_map_by_ids(["leaf_1"]) == {"leaf_1": "leaf_1"}

    def test_equivalent_to_level_1(self, dimension: CrossDimension):
        """Targeting all level-1 nodes plus root should match ancestor_maps[1]."""
        by_ids = dimension.get_ancestor_map_by_ids(["cat_a", "cat_b", "total"])
        by_level = dimension.ancestor_maps[1]
        assert by_ids == by_level

    def test_equivalent_to_level_0(self, dimension: CrossDimension):
        by_ids = dimension.get_ancestor_map_by_ids(["total"])
        by_level = dimension.ancestor_maps[0]
        assert by_ids == by_level


class TestAncestryChainsCycleProtection:
    """Edge case: malformed data with a cycle in the parent chain."""

    def test_cycle_does_not_loop_forever(self, make_contract_resource):
        contract = {
            "name": "dim_cycle",
            "description": "Cyclic dimension",
            "title": "Cycle",
            "tableschema": {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "label", "type": "string"},
                    {"name": "level", "type": "integer"},
                    {"name": "parent_id", "type": "string"},
                ],
            },
        }
        data = pd.DataFrame(
            {
                "id": ["a", "b"],
                "label": ["A", "B"],
                "level": [0, 1],
                "parent_id": ["b", "a"],  # a→b→a cycle
            }
        )
        cr = make_contract_resource(data=data, contract_dict=contract)
        dim = CrossDimension(contract_resource=cr)
        chains = dim._build_ancestry_chains()
        # chain terminates despite cycle
        assert "a" in chains
        assert "b" in chains


class TestFlexibleDimension:
    flex_contract = {
        "name": "dim_currency",
        "description": "A flexible (non-hierarchical) dimension",
        "title": "Currency",
        "contract_type": "FlexibleDimension",
        "tableschema": {
            "primaryKey": ["code"],
            "fields": [
                {"name": "code", "type": "string"},
                {"name": "label", "type": "string"},
                {"name": "description", "type": "string"},
            ],
        },
    }
    flex_data = pd.DataFrame(
        {
            "code": ["EUR", "USD"],
            "label": ["Euro", "US Dollar"],
            "description": ["", ""],
        }
    )

    def test_str(self, make_contract_resource):
        cr = make_contract_resource(
            data=self.flex_data, contract_dict=self.flex_contract
        )
        dim = CrossFlexibleDimension(contract_resource=cr)
        assert str(dim) == "FlexibleDimension(name=dim_currency)"
